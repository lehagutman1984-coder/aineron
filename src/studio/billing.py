import logging

from .models_catalog import MODEL_TIER, STAR_RATE, AGENT_BUDGET

logger = logging.getLogger(__name__)

def estimate_stars(model: str, agent: str = 'coder', planned_steps: int = 5) -> int:
    """
    Возвращает оценку числа звёзд на весь проект исходя из tier модели и реального planned_steps.
    """
    tier = MODEL_TIER.get(model, 'fast')
    rate = STAR_RATE[tier]
    base = AGENT_BUDGET.get(agent, 12)
    return int(round(rate * base * planned_steps))

def _billing_charge(project, agent, step_index, usage=None, tier_override=None):
    """
    Списывает звёзды за шаг. Учитывает prompt_tokens и completion_tokens, если usage задан.
    """
    tier = tier_override or MODEL_TIER.get(getattr(project, 'ai_model', 'fast'), 'fast')
    rate = STAR_RATE[tier]
    base = AGENT_BUDGET.get(agent, 12)
    stars = int(round(rate * base))
    tokens = 0
    if usage:
        tokens = usage.get('completion_tokens', 0) + usage.get('prompt_tokens', 0)
        # Можно пересчитать стоимость по токенам, если нужно: stars = int(math.ceil(tokens / 900 * rate))
    if getattr(project, 'stars_balance', None) is not None:
        if project.stars_balance < stars:
            from .tasks import _pause_no_funds
            _pause_no_funds(project, agent)
            return False
        project.stars_balance -= stars
        project.save(update_fields=['stars_balance'])
    # Логируем расход по шагу
    log = project.interview_data.get('billing_log', [])
    log.append({
        'step': step_index,
        'agent': agent,
        'stars': stars,
        'tokens': tokens,
    })
    project.interview_data['billing_log'] = log
    project.save(update_fields=['interview_data'])
    return True

def release_reserve(project):
    """
    Возвращает зарезервированные звёзды при завершении/ошибке пайплайна.
    """
    if getattr(project, 'stars_reserved', 0) > 0:
        project.stars_balance += project.stars_reserved
        project.stars_reserved = 0
        project.save(update_fields=['stars_balance', 'stars_reserved'])
        logger.info(f'Резерв звёзд возвращён: {project}')
