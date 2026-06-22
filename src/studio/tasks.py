# ... (остальной код не показан для краткости)
# Исправления внутри функций, где завершается пайплайн, возникает ошибка, таймаут или ручная остановка.
from .billing import release_reserve

def next_step(project_id, step_index):
    # ... (остальной код)
    if nxt >= total:
        release_reserve(project)
        # ... (остальной код завершения)
    # ... (остальной код)

def _timeout_pipeline(state, reason):
    from .sandbox import kill_sandbox
    from .billing import release_reserve
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
    publish_event(str(project.id), 'failed', {'reason': reason})

def pause_pipeline(project, reason):
    """
    Принудительная остановка пайплайна с возвратом резерва.
    """
    project.pipeline.status = 'paused_manual'
    project.pipeline.pause_reason = reason
    project.pipeline.save(update_fields=['status', 'pause_reason'])
    release_reserve(project)
# ... (остальной код)
