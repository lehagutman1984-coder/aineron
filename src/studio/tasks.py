import re
import hashlib
from celery import shared_task, chord
from django.conf import settings
from .models import StudioProject, StudioFile, StudioVersion, StudioPipelineState
from .events import publish_event
from . import sandbox
from .billing import (
    STAR_RATE, AGENT_BUDGET, can_afford, charge, refund, coder_tier_for_model,
    reserve, charge_from_reserve, release_reserve, estimate_stars,
)

QUEUE = 'studio_queue'


class InsufficientStars(Exception):
    """Raised when a user can't afford an agent run. Pauses the pipeline."""
    def __init__(self, needed):
        self.needed = needed
        super().__init__(f'Недостаточно звёзд: нужно {needed}')


def _agent_cost(agent_name: str) -> int:
    tier, budget = AGENT_BUDGET.get(agent_name, ('fast', 2000))
    return max(1, int((budget / 1000.0) * STAR_RATE[tier]))


def _billing_charge(project, agent_name: str, step_index: int, tier_override: str = None):
    """Charge stars for one agent run, emit SSE billing event, update billing_log."""
    if tier_override:
        tier, budget = AGENT_BUDGET.get(agent_name, ('fast', 2000))
        cost = max(1, int((budget / 1000.0) * STAR_RATE[tier_override]))
    else:
        cost = _agent_cost(agent_name)
    if not charge_from_reserve(cost, project):
        raise InsufficientStars(cost)
    publish_event(str(project.id), {
        'agent': agent_name, 'level': 'billing',
        'text': f'-{cost} зв. (шаг {step_index})',
    })
    log = project.interview_data.setdefault('billing_log', [])
    log.append({'agent': agent_name, 'stars': cost, 'step': step_index})
    project.save(update_fields=['interview_data'])
    return cost


def _pause_no_funds(project, needed):
    release_reserve(project)
    state = project.pipeline
    state.status = 'paused_on_loop'
    state.pause_reason = f'Недостаточно звёзд для продолжения (нужно ещё ~{needed})'
    state.save(update_fields=['status', 'pause_reason'])
    project.status = 'paused'
    project.save(update_fields=['status'])
    publish_event(str(project.id), {
        'agent': 'system', 'level': 'error',
        'text': state.pause_reason, 'type': 'paused',
    })


def _set_status(project, status):
    project.status = status
    project.save(update_fields=['status'])


def _split_steps(commits_md: str):
    """Split COMMITS.md into individual step sections by ## / ### headers."""
    return [p for p in re.split(r'\n(?=#{2,3}\s)', commits_md or '') if p.strip()]


def _get_step_text(project, step_index):
    """Extracts step text from commits_md_content by splitting on ## / ### headers."""
    parts = _split_steps(project.commits_md_content)
    return parts[step_index] if step_index < len(parts) else project.commits_md_content


def _existing_files(project):
    return {f.path: f.content for f in project.files.all()}


# ========== Agents 0-2 ==========

@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_interview(self, project_id):
    import logging
    log = logging.getLogger('studio.tasks')
    project = StudioProject.objects.get(id=project_id)
    from .agents.interviewer import InterviewerAgent
    try:
        InterviewerAgent(project).run()
        publish_event(project_id, {'agent': 'interviewer', 'level': 'info', 'text': 'Вопросы готовы'})
    except Exception as e:
        log.error('agent_interview FAILED project=%s: %s', project_id, repr(e), exc_info=True)
        if self.request.retries >= self.max_retries:
            project.status = 'draft'
            project.interview_data['interview_error'] = repr(e)
            project.save(update_fields=['status', 'interview_data'])
            publish_event(project_id, {
                'agent': 'interviewer', 'level': 'error',
                'text': 'Не удалось запустить агента-интервьюера. Обновите страницу.',
            })
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
        _billing_charge(project, 'analyst', 0)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed)
        return
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
        _billing_charge(project, 'planner', 0)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed)
        return
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


# ========== Full coding pipeline (Sprint B) ==========

@shared_task(queue=QUEUE)
def run_pipeline(project_id):
    project = StudioProject.objects.get(id=project_id)
    if project.status not in ('coding', 'ready', 'paused'):
        return
    if not can_afford(project.user, _agent_cost('coder')):
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': 'Недостаточно звёзд для запуска кодинга',
        })
        return
    planned = project.interview_data.get('planned_steps', 5)
    est = estimate_stars(project, planned_steps=planned)
    if not reserve(project.user, est, project):
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': f'Недостаточно звёзд для резервирования (~{est}). Пополните баланс.',
        })
        return
    project.status = 'coding'
    project.save(update_fields=['status'])
    state = project.pipeline
    state.status = 'running'
    state.step_index = 0
    state.iteration_count = 0
    from django.utils import timezone as _tz
    state.started_at = _tz.now()
    state.save()
    publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Запускаю sandbox...'})
    from django.conf import settings as _s
    if sandbox.count_user_sandboxes(project.user_id) >= _s.STUDIO_MAX_SANDBOXES_PER_USER:
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': 'Достигнут лимит одновременных проектов. Завершите другой проект.',
        })
        state.status = 'paused_manual'
        state.pause_reason = 'Лимит sandbox'
        state.save(update_fields=['status', 'pause_reason'])
        project.status = 'paused'
        project.save(update_fields=['status'])
        return
    try:
        cid = sandbox.spawn_sandbox(project_id, user_id=project.user_id)
        project.sandbox_container_id = cid
        project.save(update_fields=['sandbox_container_id'])
        sandbox.sync_all(project)
        if not project.files.exists():
            sandbox.write_files(cid, {'package.json': '{"name":"app","private":true}'})
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Устанавливаю зависимости...'})
        sandbox.install_deps(cid)
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Зависимости установлены'})
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
    except Exception as exc:
        import logging
        logging.getLogger('studio.tasks').error(
            'run_pipeline sandbox setup FAILED project=%s: %s', project_id, repr(exc), exc_info=True)
        try:
            if 'cid' in dir() and cid:
                sandbox.kill_sandbox(cid)
        except Exception:
            pass
        state.status = 'failed'
        state.last_error = repr(exc)
        state.save(update_fields=['status', 'last_error'])
        project.status = 'failed'
        project.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': 'Не удалось поднять sandbox. Попробуйте перезапустить.',
            'type': 'failed',
        })
        return
    project.sandbox_container_id = cid
    project.preview_port = 3000
    # Re-sync planned_steps from actual section count so next_step uses real number
    project.interview_data['planned_steps'] = (
        len(_split_steps(project.commits_md_content))
        or project.interview_data.get('planned_steps', 5)
    )
    project.save(update_fields=['sandbox_container_id', 'preview_port', 'interview_data'])
    start_step.delay(project_id, 0)


@shared_task(queue=QUEUE)
def start_step(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    if state.pause_requested or state.status in ('paused_manual', 'paused_on_loop'):
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн на паузе — шаг не запущен'})
        return
    state.step_index = step_index
    state.iteration_count = 0
    state.save(update_fields=['step_index', 'iteration_count'])
    coder_iteration.delay(project_id, step_index)


def _ensure_sandbox(project, project_id):
    """Spawn sandbox for a project that has none (e.g. resumed after limit hit)."""
    from django.conf import settings as _s
    if sandbox.count_user_sandboxes(project.user_id) >= _s.STUDIO_MAX_SANDBOXES_PER_USER:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'Достигнут лимит sandbox — продолжаем без build check',
        })
        return
    try:
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Поднимаю sandbox...'})
        cid = sandbox.spawn_sandbox(project_id, user_id=project.user_id)
        project.sandbox_container_id = cid
        project.save(update_fields=['sandbox_container_id'])
        sandbox.sync_all(project)
        if not project.files.exists():
            sandbox.write_files(cid, {'package.json': '{"name":"app","private":true}'})
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Устанавливаю зависимости...'})
        sandbox.install_deps(cid)
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Зависимости установлены'})
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
        project.preview_port = 3000
        project.save(update_fields=['preview_port'])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Sandbox готов'})
    except Exception as exc:
        import logging
        logging.getLogger('studio.tasks').warning(
            'resume sandbox spawn FAILED project=%s: %s', project_id, repr(exc))
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'Sandbox не поднялся — продолжаем без build check',
        })


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def coder_iteration(self, project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    if state.pause_requested or state.status in ('paused_manual', 'paused_on_loop'):
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн на паузе — шаг не запущен'})
        return
    state.current_task_id = self.request.id or ''
    state.save(update_fields=['current_task_id'])
    if not project.sandbox_container_id:
        _ensure_sandbox(project, project_id)
        project.refresh_from_db(fields=['sandbox_container_id', 'preview_port'])
    from .agents.coder import CoderAgent
    try:
        step_text = _get_step_text(project, step_index)
        existing = _existing_files(project)
        allowed_files = None
        if project.pipeline.iteration_count > 0 and project.pipeline.fix_plan:
            fp = project.pipeline.fix_plan
            targets = fp.get('target_files') or []
            step_text += f"\n\nИСПРАВЬ согласно FixPlan:\n{fp.get('instructions', '')}"
            if targets:
                step_text += f"\n\nИЗМЕНЯЙ ТОЛЬКО эти файлы: {', '.join(targets)}. Остальные не трогай."
                allowed_files = targets
        publish_event(project_id, {
            'agent': 'coder', 'level': 'info',
            'text': f'Шаг {step_index}, итерация {project.pipeline.iteration_count}',
        })
        agent = CoderAgent(project)
        files = agent.run(step_index, step_text, existing, allowed_files=allowed_files)
        coder_tier = coder_tier_for_model(agent.last_model)

        # Same-diff detection: pause if agent produces identical output twice in a row
        files_hash = hashlib.sha256(
            ''.join(f'{k}:{v}' for k, v in sorted(files.items())).encode()
        ).hexdigest()[:16]
        state.refresh_from_db()
        if files_hash and files_hash == state.last_files_hash:
            state.same_diff_count = (state.same_diff_count or 0) + 1
            if state.same_diff_count >= 2:
                state.status = 'paused_on_loop'
                state.pause_reason = (
                    f'Агент не может изменить код на шаге {state.step_index + 1}. '
                    'Опишите, что именно должно измениться.'
                )
                state.save(update_fields=['status', 'pause_reason', 'same_diff_count', 'last_files_hash'])
                project.status = 'paused'
                project.save(update_fields=['status'])
                publish_event(str(project.id), {
                    'agent': 'system', 'level': 'warning', 'type': 'paused',
                    'reason': state.pause_reason,
                })
                return
        else:
            state.same_diff_count = 0
        state.last_files_hash = files_hash
        state.save(update_fields=['last_files_hash', 'same_diff_count'])

        for path, content in files.items():
            StudioFile.objects.update_or_create(
                project=project, path=path,
                defaults={'content': content, 'last_modified_by': 'agent'},
            )
        project.interview_data.setdefault('last_changed', {})[str(step_index)] = list(files.keys())
        project.save(update_fields=['interview_data'])
        if project.sandbox_container_id:
            sandbox.write_files(project.sandbox_container_id, files)
            sandbox.wait_for_ready(project.sandbox_container_id, timeout=60)
        chord(
            [agent_review.s(project_id, step_index), agent_test.s(project_id, step_index)],
            merge_reports.s(project_id, step_index),
        ).apply_async()
        _billing_charge(project, 'coder', step_index, tier_override=coder_tier)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed)
        return
    except Exception as e:
        if self.request.retries >= self.max_retries:
            reason = (
                f'Кодировщик завершился ошибкой после {self.max_retries + 1} попыток: '
                f'{str(e)[:300]}'
            )
            try:
                state.refresh_from_db()
                _timeout_pipeline(state, reason)
            except Exception:
                pass
            return
        attempt = self.request.retries + 1
        total = self.max_retries + 1
        publish_event(project_id, {
            'agent': 'coder', 'level': 'warning',
            'text': (
                f'Ошибка (попытка {attempt}/{total}): {str(e)[:200]} '
                f'— повтор через 60 сек'
            ),
        })
        raise self.retry(exc=e, countdown=60)


@shared_task(queue=QUEUE)
def agent_review(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    from .agents.reviewer import ReviewerAgent
    changed_paths = project.interview_data.get('last_changed', {}).get(str(step_index), [])
    all_files = _existing_files(project)
    review_files = {p: all_files[p] for p in changed_paths if p in all_files} or all_files
    report = ReviewerAgent(project).run(
        _get_step_text(project, step_index),
        review_files,
        all_files=all_files,
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
    logs, exit_code = '', None
    if project.sandbox_container_id:
        try:
            exit_code, logs = sandbox.run_build_check(project.sandbox_container_id)
        except Exception as exc:
            logs = f'build check error: {exc}'
            exit_code = 1
    report = TesterAgent(project).run(logs, exit_code=exit_code)
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
    # Charge reviewer + tester here (not in parallel chord headers) to avoid
    # concurrent read-modify-write race on interview_data['billing_log'].
    try:
        _billing_charge(project, 'reviewer', step_index)
        _billing_charge(project, 'tester', step_index)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed)
        return

    # Error-repeat detection: escalate model on repeated identical test error
    test_errors = test.get('errors', [])
    first_error = test_errors[0]['message'][:100] if test_errors else ''
    if first_error and first_error == state.last_error_signature:
        state.error_repeat_count = (state.error_repeat_count or 0) + 1
        if state.error_repeat_count >= 2:
            from .models_catalog import ESCALATION_MAP
            escalated = ESCALATION_MAP.get(project.ai_model)
            if escalated:
                project.ai_model = escalated
                project.save(update_fields=['ai_model'])
                publish_event(str(project.id), {
                    'agent': 'system', 'level': 'info',
                    'text': f'Эскалация: переключаю на модель {escalated}',
                    'type': 'escalated', 'model': escalated,
                })
                state.error_repeat_count = 0
    else:
        state.error_repeat_count = 0
    state.last_error_signature = first_error
    state.save(update_fields=['last_error_signature', 'error_repeat_count'])

    if state.pause_requested:
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн на паузе — шаг завершён, продолжение остановлено'})
        return
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
            try:
                _billing_charge(project, 'fixer', step_index)
            except InsufficientStars as e:
                _pause_no_funds(project, e.needed)
                return
            publish_event(project_id, {
                'agent': 'fixer', 'level': 'warning',
                'text': 'Готовлю исправления',
            })
            coder_iteration.delay(project_id, step_index)
        else:
            # Reached max iterations — refund last step's agent costs
            step_refund = _agent_cost('coder') + _agent_cost('reviewer') + _agent_cost('tester')
            refund(project.user, step_refund, project)
            publish_event(project_id, {
                'agent': 'system', 'level': 'billing',
                'text': f'+{step_refund} зв. возврат (шаг не сошёлся)',
            })
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
        files = {f.path: f.content for f in project.files.all()}
        try:
            res = gitea_client.put_files_batch(
                owner, repo, files, message=f'Step {step_index}',
            )
            git_sha = (res.get('commit') or {}).get('sha', '')
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': f'Закоммичено в git (шаг {step_index})',
            })
        except Exception as exc:
            publish_event(project_id, {
                'agent': 'system', 'level': 'warning',
                'text': f'Git push failed: {exc}',
            })
    StudioVersion.objects.create(
        project=project,
        step_index=step_index,
        step_name=f'Шаг {step_index}',
        git_sha=git_sha,
        stars_spent_at_version=project.stars_spent,
    )
    if project.mode in ('semi', 'manual'):
        state = project.pipeline
        state.status = 'paused_manual'
        state.pause_reason = f'Шаг {step_index} готов — подтвердите продолжение'
        state.save(update_fields=['status', 'pause_reason'])
        project.status = 'paused'
        project.save(update_fields=['status'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'info',
            'text': state.pause_reason, 'type': 'awaiting_approval',
        })
        return
    next_step.delay(project_id, step_index)


@shared_task(queue=QUEUE)
def next_step(project_id, step_index):
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    if state.pause_requested:
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн на паузе — следующий шаг не запущен'})
        return
    total = project.interview_data.get('planned_steps', 5)
    nxt = step_index + 1
    if nxt >= total:
        release_reserve(project)
        # Kill and clear the sandbox so the frontend stops loading a dead preview
        if project.sandbox_container_id:
            try:
                sandbox.kill_sandbox(project.sandbox_container_id)
            except Exception:
                pass
        project.status = 'completed'
        project.sandbox_container_id = ''
        project.save(update_fields=['status', 'sandbox_container_id'])
        state = project.pipeline
        state.status = 'completed'
        state.pause_reason = ''
        state.resume_hint = ''
        state.pause_requested = False
        state.save(update_fields=['status', 'pause_reason', 'resume_hint', 'pause_requested'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': 'Проект завершён',
        })
        notify_project_done.delay(project_id)
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


PLAYWRIGHT_QUEUE = 'studio_playwright_queue'


@shared_task(bind=True, max_retries=1, queue=PLAYWRIGHT_QUEUE)
def crawl_spa_task(self, project_id):
    """Full JS-rendered crawl via Playwright. Runs in celery_studio_playwright (prefork, NOT gevent)."""
    from .crawler import crawl_spa
    project = StudioProject.objects.get(id=project_id)
    try:
        data = crawl_spa(project.target_url)
        project.interview_data['crawled'] = {
            'title': data['title'],
            'text': data['text'][:8000],
        }
        project.status = 'planning'
        project.save(update_fields=['interview_data', 'status'])
        agent_analyze.delay(project_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2, queue=QUEUE)
def crawl_and_analyze(self, project_id):
    """Crawl the target_url of a clone-mode project, then continue to agent_analyze."""
    from .crawler import crawl
    project = StudioProject.objects.get(id=project_id)
    try:
        publish_event(project_id, {
            'agent': 'system', 'level': 'info',
            'text': f'Анализирую сайт: {project.target_url}',
        })
        data = crawl(project.target_url)
        if len((data.get('text') or '').strip()) < 200:
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': 'SPA — рендерю через браузер...',
            })
            crawl_spa_task.delay(project_id)
            return
        project.interview_data['crawled'] = {
            'title': data['title'],
            'text': data['text'][:8000],
        }
        project.status = 'planning'
        project.save(update_fields=['interview_data', 'status'])
        agent_analyze.delay(project_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(queue=QUEUE)
def sync_manual_edit(project_id, file_id):
    """Push a manually-edited file to sandbox and Gitea after a user PATCH."""
    from . import gitea_client
    from .models import StudioFile
    project = StudioProject.objects.get(id=project_id)
    f = StudioFile.objects.get(pk=file_id, project=project)
    if project.sandbox_container_id:
        try:
            sandbox.write_files(project.sandbox_container_id, {f.path: f.content})
        except Exception as exc:
            publish_event(project_id, {
                'agent': 'system', 'level': 'warning',
                'text': f'Не удалось записать {f.path} в sandbox: {exc}',
            })
    owner = project.user.gitea_username
    repo = project.repo_url.rstrip('/').split('/')[-1] if project.repo_url else None
    if owner and repo:
        try:
            gitea_client.put_file(owner, repo, f.path, f.content,
                                  message=f'Manual edit: {f.path}')
        except Exception as exc:
            publish_event(project_id, {
                'agent': 'system', 'level': 'warning',
                'text': f'Git push failed for {f.path}: {exc}',
            })
    publish_event(project_id, {
        'agent': 'system', 'level': 'info',
        'text': f'Файл обновлён: {f.path}',
    })


@shared_task(bind=True, max_retries=2, queue=QUEUE)
def deploy_to_vercel(self, project_id):
    import requests as _rq
    project = StudioProject.objects.get(id=project_id)
    if not settings.STUDIO_VERCEL_TOKEN:
        publish_event(project_id, {'agent': 'system', 'level': 'error', 'text': 'Vercel не настроен'})
        return
    # Build-gate: verify the project builds before deploying
    if project.sandbox_container_id:
        is_next = project.target_stack == 'nextjs'
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Проверяю сборку перед деплоем...'})
        exit_code, output = sandbox.run_build_check(project.sandbox_container_id, is_nextjs=is_next)
        if exit_code != 0:
            publish_event(project_id, {
                'agent': 'system', 'level': 'error', 'type': 'deploy_failed',
                'text': f'Сборка не прошла перед деплоем. Исправьте ошибки.\n{output[-500:]}',
            })
            return
    files = [{'file': f.path, 'data': f.content} for f in project.files.all()]
    try:
        r = _rq.post(
            'https://api.vercel.com/v13/deployments',
            headers={'Authorization': f'Bearer {settings.STUDIO_VERCEL_TOKEN}'},
            json={
                'name': f'aineron-{str(project.id)[:8]}',
                'files': files,
                'projectSettings': {'framework': 'nextjs'},
            },
            timeout=60,
        )
        data = r.json()
        url = 'https://' + data.get('url', '') if data.get('url') else ''
        project.vercel_deployment_url = url
        project.save(update_fields=['vercel_deployment_url'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': f'Опубликовано: {url}' if url else 'Деплой запущен (url не получен)',
        })
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task(queue=QUEUE)
def restart_preview(project_id):
    """Re-spawn sandbox for a completed project so the user can preview it again."""
    project = StudioProject.objects.get(id=project_id)
    if project.sandbox_container_id:
        try:
            sandbox.kill_sandbox(project.sandbox_container_id)
        except Exception:
            pass
    import json as _json
    # Check if project needs a dev server (has 'dev' script) or is static HTML
    pkg_file = project.files.filter(path='package.json').first()
    has_dev_script = False
    if pkg_file:
        try:
            pkg = _json.loads(pkg_file.content)
            has_dev_script = 'dev' in pkg.get('scripts', {})
        except Exception:
            pass

    if not has_dev_script:
        # Static project: serve files directly from DB — no Docker needed
        if project.sandbox_container_id:
            try:
                sandbox.kill_sandbox(project.sandbox_container_id)
            except Exception:
                pass
            project.sandbox_container_id = ''
            project.save(update_fields=['sandbox_container_id'])
        publish_event(project_id, {'agent': 'system', 'level': 'success', 'text': 'Превью готово (статический сайт — файлы из базы)'})
        return

    # npm project with dev server — spawn sandbox
    if project.sandbox_container_id:
        try:
            sandbox.kill_sandbox(project.sandbox_container_id)
        except Exception:
            pass
    try:
        cid = sandbox.spawn_sandbox(project_id)
        project.sandbox_container_id = cid
        project.save(update_fields=['sandbox_container_id'])
        sandbox.sync_all(project)
        if not project.files.exists():
            sandbox.write_files(cid, {'package.json': '{"name":"app","private":true}'})
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Устанавливаю зависимости...'})
        sandbox.install_deps(cid)
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Зависимости установлены'})
        sandbox.isolate(cid)
        sandbox.start_dev_server(cid)
        project.preview_port = 3000
        project.save(update_fields=['preview_port'])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Sandbox запущен, ждём HTTP-сервер...'})
        ready = sandbox.wait_for_ready(cid, timeout=150, warmup=True)
        if ready:
            publish_event(project_id, {'agent': 'system', 'level': 'success', 'text': 'Превью готово'})
        else:
            _, dev_log = sandbox.exec_command(cid, 'tail -20 /tmp/dev.log 2>/dev/null || true')
            publish_event(project_id, {
                'agent': 'system', 'level': 'error',
                'text': f'Превью не ответило за 150 сек. dev.log:\n{dev_log}',
            })
    except Exception as exc:
        publish_event(project_id, {'agent': 'system', 'level': 'error', 'text': f'Не удалось перезапустить превью: {exc}'})


@shared_task(queue=QUEUE)
def delete_sandbox_file(project_id, path):
    """Remove a deleted file from the running sandbox."""
    project = StudioProject.objects.get(id=project_id)
    if project.sandbox_container_id:
        try:
            sandbox.exec_command(project.sandbox_container_id, f'rm -f {path}')
        except Exception:
            pass


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
                pid = container.labels.get('studio_project')
                container.remove(force=True)
                if pid:
                    StudioProject.objects.filter(
                        id=pid, sandbox_container_id=container.name,
                    ).update(sandbox_container_id='')
        except Exception:
            pass


@shared_task(queue=QUEUE)
def notify_project_done(project_id):
    """Send email notification when a project completes generation."""
    project = StudioProject.objects.get(id=project_id)
    prefs = (project.interview_data or {}).get('notify', {'email': True})
    if prefs.get('email'):
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            send_mail(
                subject='Проект готов',
                message=f'Ваш проект «{project.name}» сгенерирован в aineron Studio.',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@aineron.ru'),
                recipient_list=[project.user.email],
                fail_silently=True,
            )
        except Exception:
            pass


@shared_task(bind=True, max_retries=2, queue=QUEUE)
def export_to_github(self, project_id, repo_name, private):
    """Export all project files to a new GitHub repository via the GitHub API."""
    import base64
    import requests as rq
    project = StudioProject.objects.get(id=project_id)
    # 1. OAuth token via allauth (GitHub social login)
    gh_token = None
    try:
        from allauth.socialaccount.models import SocialToken
        token_obj = SocialToken.objects.filter(
            account__user=project.user, account__provider='github'
        ).first()
        if token_obj:
            gh_token = token_obj.token
    except Exception:
        pass
    # 2. Fallback: personal access token from env
    if not gh_token:
        gh_token = getattr(settings, 'GITHUB_TOKEN', '') or ''
    if not gh_token:
        publish_event(project_id, {
            'agent': 'system', 'level': 'error',
            'text': 'GitHub не подключён. Добавьте GITHUB_TOKEN в .env или войдите через GitHub.',
        })
        return
    headers = {'Authorization': f'token {gh_token}', 'Accept': 'application/vnd.github+json'}
    try:
        r = rq.post(
            'https://api.github.com/user/repos',
            headers=headers,
            json={'name': repo_name, 'private': bool(private), 'auto_init': False},
            timeout=30,
        )
        data = r.json()
        owner = data.get('owner', {}).get('login')
        if not owner:
            raise RuntimeError(data)
        for f in project.files.all():
            rq.put(
                f'https://api.github.com/repos/{owner}/{repo_name}/contents/{f.path.lstrip("/")}',
                headers=headers,
                json={'message': f'Add {f.path}', 'content': base64.b64encode(f.content.encode()).decode()},
                timeout=30,
            )
        project.github_repo_url = data.get('html_url', '')
        project.save(update_fields=['github_repo_url'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': f'Экспортировано: {project.github_repo_url}',
        })
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@shared_task(name='studio.watchdog_pipelines', queue=QUEUE)
def watchdog_pipelines():
    """Beat every 2 min: detect stalled and timed-out pipelines, kill and mark failed."""
    from django.utils import timezone
    from celery import current_app

    stall_sec = getattr(settings, 'STUDIO_STEP_STALL_SEC', 240)
    max_sec = getattr(settings, 'STUDIO_PIPELINE_MAX_SEC', 2700)
    now = timezone.now()

    for state in StudioPipelineState.objects.filter(status='running').select_related('project'):
        age_total = (now - state.started_at).total_seconds() if state.started_at else 0
        age_step = (now - state.updated_at).total_seconds() if state.updated_at else 0

        if age_total > max_sec:
            _timeout_pipeline(state, 'Пайплайн превысил максимальное время выполнения')
        elif age_step > stall_sec:
            if state.current_task_id:
                try:
                    current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')
                except Exception:
                    pass
            _timeout_pipeline(
                state,
                f'Агент завис на шаге {state.step_index + 1} (нет ответа > {stall_sec // 60} мин)',
            )


def _timeout_pipeline(state, reason):
    from .sandbox import kill_sandbox

    project = state.project
    state.status = 'failed'
    state.pause_reason = reason
    state.save(update_fields=['status', 'pause_reason'])
    project.status = 'failed'
    project.save(update_fields=['status'])
    if project.sandbox_container_id:
        try:
            kill_sandbox(project.sandbox_container_id)
        except Exception:
            pass
        project.sandbox_container_id = ''
        project.save(update_fields=['sandbox_container_id'])
    try:
        release_reserve(project)
    except Exception:
        pass
    publish_event(str(project.id), {
        'agent': 'system', 'level': 'error',
        'text': reason, 'type': 'failed',
    })
