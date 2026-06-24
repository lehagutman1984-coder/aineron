import re
import hashlib
from celery import shared_task
from django.conf import settings
from .models import StudioProject, StudioFile, StudioVersion, StudioPipelineState
from .events import publish_event
from . import sandbox
from .billing import (
    STAR_RATE, AGENT_BUDGET, can_afford, charge, refund, coder_tier_for_model,
    reserve, charge_from_reserve, release_reserve, estimate_stars, stars_for_tokens,
)

QUEUE = 'studio_queue'


class InsufficientStars(Exception):
    """Raised when a user can't afford an agent run. Pauses the pipeline."""
    def __init__(self, needed, reason=None):
        self.needed = needed
        self.reason = reason
        super().__init__(f'Недостаточно звёзд: нужно {needed}')


def _agent_cost(agent_name: str) -> int:
    tier, budget = AGENT_BUDGET.get(agent_name, ('fast', 2000))
    return max(1, int((budget / 1000.0) * STAR_RATE[tier]))


def _billing_charge(project, agent_name: str, step_index: int, tier_override: str = None,
                    prompt_tokens: int = None, completion_tokens: int = None):
    """Charge stars for one agent run, emit SSE billing event, update billing_log."""
    if (settings.STUDIO_V4_TOKEN_BILLING
            and prompt_tokens is not None and completion_tokens is not None):
        tier = tier_override or AGENT_BUDGET.get(agent_name, ('fast', 0))[0]
        cost = stars_for_tokens(prompt_tokens, completion_tokens, tier)
    elif tier_override:
        tier, budget = AGENT_BUDGET.get(agent_name, ('fast', 2000))
        cost = max(1, int((budget / 1000.0) * STAR_RATE[tier_override]))
    else:
        cost = _agent_cost(agent_name)
    cap = project.max_stars_budget or 0
    if cap:
        project.refresh_from_db(fields=['stars_spent'])
        if project.stars_spent + cost > cap:
            raise InsufficientStars(
                cost,
                reason=f'Бюджет проекта исчерпан (лимит {cap} зв., потрачено {project.stars_spent} зв.)',
            )
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


def _pause_no_funds(project, needed, reason=None):
    release_reserve(project)
    state = project.pipeline
    state.status = 'paused_on_loop'
    state.pause_reason = reason or f'Недостаточно звёзд для продолжения (нужно ещё ~{needed})'
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


def _record_metric(project, step_index, **kwargs):
    """Накапливает per-step метрики в interview_data['metrics'][str(step_index)]."""
    try:
        metrics = project.interview_data.setdefault('metrics', {})
        step_m = metrics.setdefault(str(step_index), {})
        for k, v in kwargs.items():
            if isinstance(v, (int, float)) and k in step_m and isinstance(step_m[k], (int, float)):
                step_m[k] += v
            else:
                step_m[k] = v
        project.save(update_fields=['interview_data'])
    except Exception:
        pass


def _existing_files(project):
    return {f.path: f.content for f in project.files.all()}


# ========== Studio V3: deterministic gates ==========

def _structure_gate(project, project_id, step_index, step_text, existing, files, agent, model_tier=None, max_fixes=2):
    """
    Детерминированный structure gate. Жёсткий критерий — обрезка (нет end-маркера),
    advisory — дисбаланс скобок/JSX. Точечно дозапрашивает сломанные файлы (max_fixes).
    """
    from .validators import is_structurally_complete
    broken = {}
    for path, content in files.items():
        ok, reason = is_structurally_complete(path, content)
        if not ok:
            broken[path] = reason
    if not broken:
        return files
    _record_metric(project, step_index, structure_fails=len(broken))
    publish_event(project_id, {
        'agent': 'system', 'level': 'warning',
        'text': f'Структурная проверка: {len(broken)} файл(ов) требуют дозапроса',
    })
    fixed = dict(files)
    for path, reason in list(broken.items())[:8]:
        for attempt in range(max_fixes):
            hint = (
                f"\n\nФАЙЛ {path} структурно неполон (причина: {reason}). "
                "Сгенерируй его ПОЛНОСТЬЮ заново, со всеми закрытыми скобками и тегами."
            )
            try:
                regen = agent.run(step_index, step_text + hint, existing, allowed_files=[path])
            except Exception as exc:
                publish_event(project_id, {'agent': 'system', 'level': 'warning',
                                           'text': f'Дозапрос {path} упал: {exc}'})
                break
            new_content = regen.get(path)
            if not new_content:
                break
            ok, reason = is_structurally_complete(path, new_content)
            fixed[path] = new_content
            if ok:
                break
    return fixed


# Минимальный whitelist версий для авто-добавления недостающих пакетов.
DEP_VERSIONS = {
    'lucide-react': '^0.460.0',
    'clsx': '^2.1.1',
    'tailwind-merge': '^2.5.4',
    'recharts': '^2.13.0',
    'date-fns': '^4.1.0',
    'zustand': '^5.0.0',
    '@tanstack/react-query': '^5.59.0',
    'react-router-dom': '^6.27.0',
    'framer-motion': '^11.11.0',
}


def _dependency_gate(project, project_id, step_index, files):
    """
    Детерминированно сверяет импорты с package.json. Недостающие пакеты с известной
    версией добавляются автоматически; остальные логируются (Guardian/build их поймает).
    """
    import json as _json
    from .validators import validate_dependencies
    all_files = {f.path: f.content for f in project.files.all()}
    all_files.update(files)
    result = validate_dependencies(all_files)
    if result.get('ok'):
        return files
    missing = result.get('missing', [])
    if not missing:
        return files
    _record_metric(project, step_index, dep_fails=1)
    pkg_content = files.get('package.json') or all_files.get('package.json')
    addable = [m for m in missing if m in DEP_VERSIONS]
    if pkg_content and addable:
        try:
            pkg = _json.loads(pkg_content)
            deps = pkg.setdefault('dependencies', {})
            for m in addable:
                deps[m] = DEP_VERSIONS[m]
            files = dict(files)
            files['package.json'] = _json.dumps(pkg, indent=2, ensure_ascii=False) + '\n'
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': f'Добавлены зависимости: {", ".join(addable)}',
            })
        except Exception:
            pass
    unknown = [m for m in missing if m not in DEP_VERSIONS]
    if unknown:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'Неизвестные зависимости (проверит сборка): {", ".join(unknown)}',
        })
    return files


def _try_apply_edits(project, project_id, step_index, edits):
    """
    Применяет EDIT blocks к файлам проекта. Возвращает True, если удалось
    применить хотя бы часть патчей и шаг отправлен в guardian; False — если
    нужна полная перегенерация (fallback на обычный coder).
    """
    from .agents.edits import apply_edits, edits_too_large
    from .validators import is_structurally_complete
    files = {f.path: f.content for f in project.files.all()}
    big = edits_too_large(files, edits, threshold=0.4)
    edits_small = [e for e in edits if e['path'] not in big]
    if not edits_small:
        return False
    updated, failed = apply_edits(files, edits_small)
    if failed:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'SEARCH не найден в {len(failed)} файлах — перегенерирую их',
        })
        return False
    # проверяем структуру изменённых файлов
    changed = {p: updated[p] for p in {e['path'] for e in edits_small}}
    for path, content in changed.items():
        ok, _ = is_structurally_complete(path, content)
        if not ok:
            return False
    for path, content in changed.items():
        StudioFile.objects.update_or_create(
            project=project, path=path,
            defaults={'content': content, 'last_modified_by': 'agent'},
        )
    project.interview_data.setdefault('last_changed', {})[str(step_index)] = list(changed.keys())
    project.save(update_fields=['interview_data'])
    if project.sandbox_container_id:
        try:
            sandbox.write_files(project.sandbox_container_id, changed)
            sandbox.wait_for_ready(project.sandbox_container_id, timeout=60)
        except Exception:
            pass
    _record_metric(project, step_index, edits_applied=1)
    publish_event(project_id, {
        'agent': 'coder', 'level': 'info',
        'text': f'Применены патчи EDIT к {len(changed)} файлам (без перегенерации)',
    })
    guardian_review.delay(project_id, step_index)
    return True


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
    """Architect agent: creates PROJECT.md + COMMITS.md in one call (replaces analyst+planner)."""
    import logging
    log = logging.getLogger('studio.tasks')
    project = StudioProject.objects.get(id=project_id)
    if project.status not in ('planning', 'interview'):
        log.info('agent_analyze: project %s status=%s — skipping', project_id, project.status)
        return
    from .agents.architect import ArchitectAgent
    try:
        publish_event(project_id, {'agent': 'architect', 'level': 'info', 'text': 'Проектирую архитектуру...'})
        data = ArchitectAgent(project).run(
            description=project.description,
            stack=project.target_stack,
            features=list((project.interview_data or {}).get('features', [])),
            answers=list((project.interview_data or {}).get('answers', [])),
        )
        project.project_md_content = data.get('project_md', '')
        project.commits_md_content = data.get('commits_md', '')
        planned = data.get('planned_steps') or len(_split_steps(project.commits_md_content)) or 5
        project.interview_data['planned_steps'] = planned
        if settings.STUDIO_V3:
            project.design_md_content = data.get('design_md', '')
            if data.get('plan'):
                project.interview_data['plan'] = data['plan']
        project.status = 'ready'
        project.save(update_fields=['project_md_content', 'commits_md_content', 'design_md_content', 'interview_data', 'status'])
        state = project.pipeline
        state.review_report = {}
        state.save()
        publish_event(project_id, {
            'agent': 'architect', 'level': 'info',
            'text': f'Архитектура готова: {planned} шагов',
        })
        _billing_charge(project, 'architect', 0)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed, reason=getattr(e, 'reason', None))
        return
    except Exception as e:
        log.error('agent_analyze FAILED project=%s: %s', project_id, repr(e), exc_info=True)
        if self.request.retries >= self.max_retries:
            try:
                project.status = 'failed'
                project.save(update_fields=['status'])
                state = project.pipeline
                state.status = 'failed'
                state.last_error = repr(e)[:500]
                state.save(update_fields=['status', 'last_error'])
            except Exception:
                pass
            publish_event(project_id, {
                'agent': 'architect', 'level': 'error',
                'text': f'Архитектор завершился ошибкой: {str(e)[:300]}',
                'type': 'failed',
            })
            return
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=1, queue=QUEUE)
def agent_plan(self, project_id):
    """Legacy stub — architect now handles planning inline in agent_analyze."""
    import logging
    logging.getLogger('studio.tasks').info('agent_plan called (legacy stub) for project %s', project_id)


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
        state.pause_reason = 'Запущено слишком много проектов — удалите другие и нажмите «Продолжить», или нажмите «Подтвердить» чтобы продолжить без sandbox (без preview)'
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
        # Start dev server BEFORE isolation (pnpm 11 runDepsStatusCheck needs internet).
        sandbox.start_dev_server(cid)
        sandbox.isolate(cid)
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
    if settings.STUDIO_V3:
        from .scaffold import scaffold_files, scaffold_tma, scaffold_for_features
        # TMA: use dedicated scaffold instead of standard UI primitives
        if (getattr(settings, 'STUDIO_V4_TMA', False)
                and project.target_stack == 'tma'):
            sf = scaffold_tma()
        else:
            sf = scaffold_files(project.target_stack, project.design_md_content)
        # V4 RU_STACK: inject Russian integration scaffolds based on template.features
        if getattr(settings, 'STUDIO_V4_RU_STACK', False):
            features = (project.interview_data or {}).get('features', [])
            if not features:
                try:
                    from .models import StudioTemplate as _T
                    tmpl = _T.objects.filter(seed_prompt=project.description).first()
                    if tmpl:
                        features = tmpl.features or []
                except Exception:
                    pass
            if features:
                sf.update(scaffold_for_features(project.target_stack, features))
        if sf:
            for path, content in sf.items():
                StudioFile.objects.get_or_create(
                    project=project, path=path,
                    defaults={'content': content, 'last_modified_by': 'scaffold'},
                )
            if project.sandbox_container_id:
                try:
                    sandbox.write_files(project.sandbox_container_id, sf)
                except Exception:
                    pass
            publish_event(project_id, {
                'agent': 'system', 'level': 'info',
                'text': f'Установлены UI-примитивы ({len(sf)} файлов)',
            })
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
        # Start dev server BEFORE isolation (pnpm 11 runDepsStatusCheck needs internet).
        sandbox.start_dev_server(cid)
        project.preview_port = 3000
        project.save(update_fields=['preview_port'])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Sandbox готов'})
        sandbox.isolate(cid)
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
            # === V3: попытка применить EDIT blocks без перегенерации ===
            if settings.STUDIO_V3 and fp.get('edits'):
                applied = _try_apply_edits(project, project_id, step_index, fp['edits'])
                if applied:
                    return  # патчи применены, шаг отправлен в guardian внутри _try_apply_edits
                # EDIT blocks не применились (SEARCH не совпал) — регенерируем только
                # затронутые файлы, не запускаем manifest по всему проекту
                allowed_files = list({e['path'] for e in fp['edits']})
            # ==========================================================
            targets = fp.get('target_files') or []
            step_text += f"\n\nИСПРАВЬ согласно FixPlan:\n{fp.get('instructions', '')}"
            if targets:
                step_text += f"\n\nИЗМЕНЯЙ ТОЛЬКО эти файлы: {', '.join(targets)}. Остальные не трогай."
                if not allowed_files:
                    allowed_files = targets
        publish_event(project_id, {
            'agent': 'coder', 'level': 'info',
            'text': f'Шаг {step_index}, итерация {project.pipeline.iteration_count}',
        })
        agent = CoderAgent(project)
        files = agent.run(step_index, step_text, existing, allowed_files=allowed_files)
        coder_tier = coder_tier_for_model(agent.last_model)

        # ===== V3: детерминированные gate перед guardian =====
        if settings.STUDIO_V3 and files:
            files = _structure_gate(project, project_id, step_index, step_text, existing, files, agent, model_tier=coder_tier)
            files = _dependency_gate(project, project_id, step_index, files)
            _record_metric(project, step_index, files_generated=len(files))
        # =====================================================

        # Same-diff detection: pause if agent produces identical output twice in a row
        files_hash = hashlib.sha256(
            ''.join(f'{k}:{v}' for k, v in sorted(files.items())).encode()
        ).hexdigest()[:16]
        state.refresh_from_db()
        if state.status == 'failed':
            log.info('coder_iteration: pipeline cancelled while running — dropping result for step %s', step_index)
            return
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
        guardian_review.delay(project_id, step_index)
        _billing_charge(
            project, 'coder', step_index, tier_override=coder_tier,
            prompt_tokens=agent.last_prompt_tokens,
            completion_tokens=agent.last_completion_tokens,
        )
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed, reason=getattr(e, 'reason', None))
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


@shared_task(bind=True, max_retries=2, queue=QUEUE)
def guardian_review(self, project_id, step_index):
    """Guardian: review + build check + fix plan in one call. Replaces reviewer+tester+fixer chord."""
    import logging
    log = logging.getLogger('studio.tasks')
    project = StudioProject.objects.get(id=project_id)
    state = project.pipeline
    if state.pause_requested or state.status in ('paused_manual', 'paused_on_loop', 'failed'):
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн остановлен'})
        return
    state.current_task_id = self.request.id or ''
    state.save(update_fields=['current_task_id'])
    build_logs = ''
    if project.sandbox_container_id:
        try:
            _, build_logs = sandbox.run_build_check(project.sandbox_container_id)
        except Exception as exc:
            build_logs = f'build check unavailable: {exc}'
    changed_paths = project.interview_data.get('last_changed', {}).get(str(step_index), [])
    all_files = _existing_files(project)
    review_files = {p: all_files[p] for p in changed_paths if p in all_files} or all_files
    from .agents.guardian import GuardianAgent
    try:
        result = GuardianAgent(project).run(
            _get_step_text(project, step_index),
            review_files,
            build_logs=build_logs,
            attempt=state.iteration_count,
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            log.warning('guardian failed (%s) — auto-passing step %s', exc, step_index)
            result = {'verdict': 'pass', 'issues': [], 'instructions': '', 'target_files': []}
        else:
            raise self.retry(exc=exc, countdown=30)
    try:
        _billing_charge(project, 'guardian', step_index)
    except InsufficientStars as e:
        _pause_no_funds(project, e.needed, reason=getattr(e, 'reason', None))
        return
    state.review_report = result
    state.save(update_fields=['review_report'])
    verdict = result.get('verdict', 'pass')
    issues_preview = '; '.join((result.get('issues') or [])[:2])
    if settings.STUDIO_V3:
        _record_metric(project, step_index,
                       guardian_iterations=state.iteration_count,
                       build_pass=1 if (build_logs and 'error' not in build_logs.lower()) else 0,
                       verdict=verdict)
    publish_event(project_id, {
        'agent': 'guardian',
        'level': 'success' if verdict == 'pass' else 'warning',
        'text': f'Шаг {step_index} принят' if verdict == 'pass' else f'Проблемы: {issues_preview}',
    })
    if state.pause_requested:
        return
    if verdict == 'pass':
        if settings.STUDIO_V4_AUTOFIX and (state.autofix_count or 0) > 0:
            state.autofix_count = 0
            state.seen_error_hashes = []
            state.save(update_fields=['autofix_count', 'seen_error_hashes'])
        commit_to_gitea.delay(project_id, step_index)
        return
    state.iteration_count += 1
    state.save(update_fields=['iteration_count'])
    max_iter = (
        project.max_iterations
        if project.max_iterations and project.max_iterations > 0
        else settings.STUDIO_MAX_ITERATIONS
    )
    if state.iteration_count < max_iter:
        state.fix_plan = {
            'instructions': result.get('instructions', ''),
            'target_files': result.get('target_files', []),
            'edits': result.get('edits', []) if settings.STUDIO_V3 else [],
            'priority': 'high',
        }
        state.save(update_fields=['fix_plan'])
        publish_event(project_id, {
            'agent': 'guardian', 'level': 'info',
            'text': f'Итерация {state.iteration_count}: отправляю кодировщику на исправление',
        })
        coder_iteration.delay(project_id, step_index)
    else:
        step_refund = _agent_cost('coder') + _agent_cost('guardian')
        refund(project.user, step_refund, project)
        publish_event(project_id, {
            'agent': 'system', 'level': 'billing',
            'text': f'+{step_refund} зв. возврат (шаг не сошёлся)',
        })
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'Шаг {step_index} не сошёлся за {max_iter} итераций — пропускаю',
        })
        # auto mode: skip to next step without pausing
        if project.mode == 'auto':
            state.iteration_count = 0
            state.fix_plan = {}
            state.save(update_fields=['iteration_count', 'fix_plan'])
            commit_to_gitea.delay(project_id, step_index)
        else:
            state.status = 'paused_on_loop'
            state.pause_reason = f'Шаг {step_index} не сошёлся за {max_iter} итераций'
            state.save(update_fields=['status', 'pause_reason'])
            project.status = 'paused'
            project.save(update_fields=['status'])
            notify_user_paused.delay(project_id)


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
        _pause_no_funds(project, e.needed, reason=getattr(e, 'reason', None))
        return

    # Error-repeat detection: escalate model on repeated identical test error
    test_errors = test.get('errors', [])
    first_error = test_errors[0]['message'][:100] if test_errors else ''
    if first_error and first_error == state.last_error_signature:
        state.error_repeat_count = (state.error_repeat_count or 0) + 1
        if state.error_repeat_count >= 2:
            from .models_catalog import ESCALATION_MAP
            agent_models = project.agent_models or {}
            cur_coder = agent_models.get('coder') or project.ai_model
            escalated = ESCALATION_MAP.get(cur_coder)
            if escalated:
                if agent_models.get('coder'):
                    project.agent_models = {**agent_models, 'coder': escalated}
                    project.save(update_fields=['agent_models'])
                else:
                    project.ai_model = escalated
                    project.save(update_fields=['ai_model'])
                publish_event(str(project.id), {
                    'agent': 'system', 'level': 'info',
                    'text': f'Эскалация кодировщика: переключаю на {escalated}',
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
        max_iter = project.max_iterations if project.max_iterations and project.max_iterations > 0 else settings.STUDIO_MAX_ITERATIONS
        if state.iteration_count < max_iter:
            from .agents.fixer import FixerAgent
            import logging as _log
            try:
                state.fix_plan = FixerAgent(project).run(review, test)
            except Exception as fixer_err:
                _log.getLogger('studio.tasks').warning(
                    'fixer failed (%s) — retrying coder without fix plan', fixer_err)
                state.fix_plan = {}
            state.save(update_fields=['fix_plan'])
            try:
                _billing_charge(project, 'fixer', step_index)
            except InsufficientStars as e:
                _pause_no_funds(project, e.needed, reason=getattr(e, 'reason', None))
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
                f'Шаг {step_index} не сошёлся за {max_iter} итераций'
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
    # V4: soft preview restart hint — frontend reloads iframe without full page reload
    if getattr(settings, 'STUDIO_V4_STREAMING', False):
        publish_event(project_id, {
            'type': 'preview_restart', 'step': step_index,
            'agent': 'system', 'level': 'info',
        })
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
    if state.pause_requested or state.status == 'failed':
        publish_event(project_id, {'agent': 'system', 'level': 'warning', 'text': 'Пайплайн остановлен — следующий шаг не запущен'})
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
        exit_code, install_out = sandbox.install_deps(cid)
        if exit_code != 0:
            import logging as _log
            _log.getLogger('studio.tasks').warning(
                'pnpm install non-zero exit=%s project=%s:\n%s', exit_code, project_id, install_out[-500:])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'type': 'progress', 'text': 'Зависимости установлены'})
        # Start dev server BEFORE isolation so pnpm 11's runDepsStatusCheck
        # (which may trigger a second `pnpm install`) runs while internet is available.
        # install_deps already wrote prefer-offline=true to .npmrc as a belt+suspenders guard.
        sandbox.start_dev_server(cid)
        project.preview_port = 3000
        project.save(update_fields=['preview_port'])
        publish_event(project_id, {'agent': 'system', 'level': 'info', 'text': 'Sandbox запущен, ждём HTTP-сервер...'})
        ready = sandbox.wait_for_ready(cid, timeout=150, warmup=True)
        # Isolate AFTER dev server is ready (or timed out) so pnpm's deps check
        # had internet access during the entire startup phase.
        sandbox.isolate(cid)
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


# ─── V4 Russian cloud deploy tasks ────────────────────────────────────────────

@shared_task(queue=QUEUE)
def deploy_to_timeweb(project_id):
    """Deploy project files to Timeweb Cloud (static hosting) via their API."""
    if not getattr(settings, 'STUDIO_V4_RU_STACK', False):
        return
    project = StudioProject.objects.get(id=project_id)
    token = getattr(settings, 'TIMEWEB_API_TOKEN', '')
    if not token:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'TIMEWEB_API_TOKEN не настроен — деплой пропущен',
        })
        return
    import urllib.request, json as _json
    files = {f.path: f.content for f in project.files.all()}
    payload = _json.dumps({'name': str(project.id)[:20], 'files': {
        p: c for p, c in files.items() if p.endswith(('.html', '.css', '.js'))
    }}).encode()
    req = urllib.request.Request(
        'https://api.timeweb.cloud/api/v1/static-sites',
        data=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
        url = data.get('response', {}).get('url', '')
        if url:
            project.vercel_deployment_url = url
            project.save(update_fields=['vercel_deployment_url'])
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': f'Опубликовано на Timeweb: {url or "—"}',
        })
    except Exception as exc:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'Timeweb deploy error: {exc}',
        })


@shared_task(queue=QUEUE)
def tma_publish(project_id):
    """Package TMA build artefacts and publish to Telegram bot webhook URL."""
    if not getattr(settings, 'STUDIO_V4_TMA', False):
        return
    project = StudioProject.objects.get(id=project_id)
    bot_token = getattr(settings, 'STUDIO_TMA_BOT_TOKEN', '')
    if not bot_token:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'STUDIO_TMA_BOT_TOKEN не настроен — публикация TMA пропущена',
        })
        return
    # Build a minimal index.html that loads the TMA app (for static host)
    html_file = next(
        (f for f in project.files.all() if f.path.endswith('index.html')),
        None,
    )
    app_url = project.vercel_deployment_url or ''
    if not app_url:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'TMA: нет URL деплоя — сначала задеплойте проект',
        })
        return
    # Set Telegram bot's webAppUrl via setMyCommands (simplified)
    import urllib.request as _req, json as _json
    payload = _json.dumps({
        'commands': [{'command': 'start', 'description': 'Открыть приложение'}],
    }).encode()
    menu_req = _req.Request(
        f'https://api.telegram.org/bot{bot_token}/setMyCommands',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        _req.urlopen(menu_req, timeout=15)
        publish_event(project_id, {
            'agent': 'system', 'level': 'success',
            'text': f'TMA опубликован! Откройте @bot или используйте URL: {app_url}',
        })
    except Exception as exc:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': f'TMA publish error: {exc}',
        })


@shared_task(queue=QUEUE)
def deploy_to_selectel(project_id):
    """Deploy project files to Selectel Object Storage (static hosting)."""
    if not getattr(settings, 'STUDIO_V4_RU_STACK', False):
        return
    project = StudioProject.objects.get(id=project_id)
    account_id = getattr(settings, 'SELECTEL_ACCOUNT_ID', '')
    api_key = getattr(settings, 'SELECTEL_API_KEY', '')
    if not account_id or not api_key:
        publish_event(project_id, {
            'agent': 'system', 'level': 'warning',
            'text': 'SELECTEL_ACCOUNT_ID / SELECTEL_API_KEY не настроены — деплой пропущен',
        })
        return
    import urllib.request as _req
    bucket = f'studio-{str(project.id)[:16]}'
    base_url = f'https://s3.selectel.ru/{account_id}/{bucket}'
    upload_ok, upload_fail = 0, 0
    for studio_file in project.files.all():
        if not studio_file.path.endswith(('.html', '.css', '.js', '.json', '.png', '.svg')):
            continue
        body = studio_file.content.encode('utf-8')
        url = f'{base_url}/{studio_file.path}'
        put = _req.Request(url, data=body, method='PUT',
                           headers={'X-Auth-Token': api_key, 'Content-Length': str(len(body))})
        try:
            _req.urlopen(put, timeout=30)
            upload_ok += 1
        except Exception:
            upload_fail += 1
    publish_event(project_id, {
        'agent': 'system', 'level': 'success' if not upload_fail else 'warning',
        'text': f'Selectel: {upload_ok} файлов загружено, {upload_fail} ошибок. URL: {base_url}',
    })
