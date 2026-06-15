import re
from celery import shared_task, chord
from django.conf import settings
from .models import StudioProject, StudioFile, StudioVersion
from .events import publish_event
from . import sandbox

QUEUE = 'studio_queue'


def _set_status(project, status):
    project.status = status
    project.save(update_fields=['status'])


def _get_step_text(project, step_index):
    """Extracts step text from commits_md_content by splitting on ## / ### headers."""
    parts = [p for p in re.split(r'\n(?=#{2,3}\s)', project.commits_md_content) if p.strip()]
    return parts[step_index] if step_index < len(parts) else project.commits_md_content


def _existing_files(project):
    return {f.path: f.content for f in project.files.all()}


# ========== Agents 0-2 ==========

@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_interview(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.interviewer import InterviewerAgent
    try:
        InterviewerAgent(project).run()
        publish_event(project_id, {'agent': 'interviewer', 'level': 'info', 'text': 'Вопросы готовы'})
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_analyze(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.analyst import AnalystAgent
    try:
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'Анализирую требования...'})
        AnalystAgent(project).run()
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'PROJECT.md готов'})
        agent_plan.delay(project_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_plan(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.planner import PlannerAgent
    try:
        publish_event(project_id, {'agent': 'planner', 'level': 'info', 'text': 'Составляю план...'})
        md, steps = PlannerAgent(project).run()
        state = project.pipeline
        state.review_report = {}
        state.save()
        project.interview_data['planned_steps'] = steps
        project.save(update_fields=['interview_data'])
        _set_status(project, 'ready')
        publish_event(project_id, {
            'agent': 'planner', 'level': 'info',
            'text': f'COMMITS.md готов: {steps} шагов',
        })
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


# ========== Full coding pipeline (Sprint B) ==========

@shared_task(queue=QUEUE)
def run_pipeline(project_id):
    project = StudioProject.objects.get(id=project_id)
    project.status = 'coding'
    project.save(update_fields=['status'])
    state = project.pipeline
    state.status = 'running'
    state.step_index = 0
    state.iteration_count = 0
    state.save()
    publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Запускаю sandbox...'})
    cid = sandbox.spawn_sandbox(project_id)
    initial_files = _existing_files(project) or {'package.json': '{"name":"app","private":true}'}
    sandbox.write_files(cid, initial_files)
    sandbox.install_deps(cid)
    sandbox.isolate(cid)
    sandbox.start_dev_server(cid)
    project.sandbox_container_id = cid
    project.preview_port = 3000
    project.save(update_fields=['sandbox_container_id', 'preview_port'])
    start_step.delay(project_id, 0)


@shared_task(queue=QUEUE)
def start_step(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    state.step_index = step_index
    state.iteration_count = 0
    state.save(update_fields=['step_index', 'iteration_count'])
    coder_iteration.delay(project_id, step_index)


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def coder_iteration(self, project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.coder import CoderAgent
    try:
        step_text = _get_step_text(project, step_index)
        existing = _existing_files(project)
        if project.pipeline.iteration_count > 0 and project.pipeline.fix_plan:
            step_text += (
                f"\n\nИСПРАВЬ согласно FixPlan:\n"
                f"{project.pipeline.fix_plan.get('instructions', '')}"
            )
        publish_event(project_id, {
            'agent': 'coder', 'level': 'info',
            'text': f'Шаг {step_index}, итерация {project.pipeline.iteration_count}',
        })
        files = CoderAgent(project).run(step_index, step_text, existing)
        for path, content in files.items():
            StudioFile.objects.update_or_create(
                project=project, path=path,
                defaults={'content': content, 'last_modified_by': 'agent'},
            )
        if project.sandbox_container_id:
            sandbox.write_files(project.sandbox_container_id, files)
        chord(
            [agent_review.s(project_id, step_index), agent_test.s(project_id, step_index)],
            merge_reports.s(project_id, step_index),
        ).apply_async()
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(queue=QUEUE)
def agent_review(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.reviewer import ReviewerAgent
    report = ReviewerAgent(project).run(
        _get_step_text(project, step_index),
        _existing_files(project),
    )
    publish_event(project_id, {
        'agent': 'reviewer', 'level': 'info',
        'text': report.get('summary', ''),
    })
    return {'kind': 'review', 'report': report}


@shared_task(queue=QUEUE)
def agent_test(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.tester import TesterAgent
    logs = ''
    if project.sandbox_container_id:
        logs = '\n'.join(sandbox.get_logs_stream(project.sandbox_container_id))
    report = TesterAgent(project).run(logs)
    publish_event(project_id, {
        'agent': 'tester', 'level': 'info',
        'text': report.get('summary', ''),
    })
    return {'kind': 'test', 'report': report}


@shared_task(queue=QUEUE)
def merge_reports(results, project_id, step_index):
    """CHORD CALLBACK. results order is NOT guaranteed — select by kind."""
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    review = next((r['report'] for r in results if r['kind'] == 'review'), {})
    test = next((r['report'] for r in results if r['kind'] == 'test'), {})
    state.review_report = review
    state.test_report = test
    state.save(update_fields=['review_report', 'test_report'])
    if review.get('passed') and test.get('passed'):
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': f'Шаг {step_index} пройден',
        })
        commit_to_gitea.delay(project_id, step_index)
    else:
        state.iteration_count += 1
        state.save(update_fields=['iteration_count'])
        if state.iteration_count < settings.STUDIO_MAX_ITERATIONS:
            from .agents.fixer import FixerAgent
            state.fix_plan = FixerAgent(project).run(review, test)
            state.save(update_fields=['fix_plan'])
            publish_event(project_id, {
                'agent': 'fixer', 'level': 'warning',
                'text': 'Готовлю исправления',
            })
            coder_iteration.delay(project_id, step_index)
        else:
            state.status = 'paused_on_loop'
            state.pause_reason = (
                f'Шаг {step_index} не сошёлся за {settings.STUDIO_MAX_ITERATIONS} итераций'
            )
            state.save(update_fields=['status', 'pause_reason'])
            project.status = 'paused'
            project.save(update_fields=['status'])
            notify_user_paused.delay(project_id)


@shared_task(queue=QUEUE)
def commit_to_gitea(project_id, step_index):
    """Push step files to Gitea and record a StudioVersion."""
    from . import gitea_client
    project = StudioProject.objects.get(id=project_id)
    owner = project.user.gitea_username
    repo = project.repo_url.rstrip('/').split('/')[-1] if project.repo_url else None
    git_sha = ''
    if owner and repo:
        for f in project.files.all():
            try:
                res = gitea_client.put_file(
                    owner, repo, f.path, f.content,
                    message=f'Step {step_index}: {f.path}',
                )
                git_sha = (res.get('commit') or {}).get('sha', git_sha)
            except Exception as exc:
                publish_event(project_id, {
                    'agent': 'system', 'level': 'warning',
                    'text': f'Git push failed for {f.path}: {exc}',
                })
        publish_event(project_id, {
            'agent': 'system', 'level': 'info',
            'text': f'Закоммичено в git (шаг {step_index})',
        })
    StudioVersion.objects.create(
        project=project,
        step_index=step_index,
        step_name=f'Шаг {step_index}',
        git_sha=git_sha,
        stars_spent_at_version=project.stars_spent,
    )
    next_step.delay(project_id, step_index)


@shared_task(queue=QUEUE)
def next_step(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    total = project.interview_data.get('planned_steps', 5)
    nxt = step_index + 1
    if nxt >= total:
        project.status = 'completed'
        project.save(update_fields=['status'])
        project.pipeline.status = 'completed'
        project.pipeline.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': 'Проект завершён',
        })
    else:
        start_step.delay(project_id, nxt)


@shared_task(queue=QUEUE)
def notify_user_paused(project_id):
    project = StudioProject.objects.get(id=project_id)
    publish_event(project_id, {
        'agent': 'system', 'level': 'error',
        'text': project.pipeline.pause_reason,
        'type': 'paused',
    })


@shared_task(queue=QUEUE)
def rollback_to_version(project_id, version_id):
    """Restore project files from a Gitea git_sha snapshot."""
    from . import gitea_client
    project = StudioProject.objects.get(id=project_id)
    version = StudioVersion.objects.get(id=version_id, project=project)
    owner = project.user.gitea_username
    repo = project.repo_url.rstrip('/').split('/')[-1] if project.repo_url else None
    if owner and repo and version.git_sha:
        for studio_file in project.files.all():
            content = gitea_client.get_file_content(owner, repo, studio_file.path, ref=version.git_sha)
            if content:
                studio_file.content = content
                studio_file.last_modified_by = 'rollback'
                studio_file.save(update_fields=['content', 'last_modified_by'])
        if project.sandbox_container_id:
            files = {f.path: f.content for f in project.files.all()}
            sandbox.write_files(project.sandbox_container_id, files)
    publish_event(project_id, {
        'agent': 'system', 'level': 'info',
        'text': f'Откат к шагу {version.step_index} ({version.git_sha[:7] if version.git_sha else "нет sha"})',
    })


@shared_task(queue=QUEUE)
def reap_stale_sandboxes():
    """Beat: removes studio containers older than N hours."""
    import datetime
    client = sandbox.get_docker()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=6)
    for container in client.containers.list(filters={'label': 'studio_project'}):
        created_str = container.attrs.get('Created', '')
        try:
            created = datetime.datetime.fromisoformat(created_str[:19])
            if created < cutoff:
                container.remove(force=True)
        except Exception:
            pass
