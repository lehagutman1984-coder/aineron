import tiktoken
from .models import StudioProject
from .models_catalog import MODEL_TIER

STAR_RATE = {'fast': 1, 'coder': 1.7, 'smart': 3}

AGENT_BUDGET = {
    'interviewer': ('fast', 2000),
    'analyst': ('smart', 6000),
    'planner': ('smart', 8000),
    'coder': ('fast', 12000),
    'reviewer': ('smart', 6000),
    'tester': ('fast', 4000),
    'fixer': ('smart', 5000),
}


def count_tokens(text: str, model: str = 'gpt-4') -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding('cl100k_base')
    return len(enc.encode(text or ''))


def estimate_stars(project: StudioProject, planned_steps: int = 5) -> int:
    total = 0.0
    desc_tokens = count_tokens(project.description) + count_tokens(str(project.interview_data))
    ai_tier = MODEL_TIER.get(getattr(project, 'ai_model', ''), 'fast')
    for agent, (tier, budget) in AGENT_BUDGET.items():
        effective_tier = ai_tier if agent in ('coder', 'reviewer', 'fixer') else tier
        loops = planned_steps if agent in ('coder', 'reviewer', 'tester') else 1
        toks = budget + (desc_tokens if agent in ('analyst', 'planner') else 0)
        total += (toks / 1000.0) * STAR_RATE.get(effective_tier, STAR_RATE['fast']) * loops
    return int(total) + 1


def coder_tier_for_model(model: str) -> str:
    """Return billing tier based on model id used by CoderAgent."""
    return MODEL_TIER.get(model, 'fast')


def can_afford(user, amount: int) -> bool:
    return user.pages_count >= amount


def charge(user, amount: int, project: StudioProject):
    user.spend_pages(amount)
    project.stars_spent += amount
    project.save(update_fields=['stars_spent'])


def refund(user, amount: int, project: StudioProject):
    user.add_pages(amount)
    project.stars_spent = max(0, project.stars_spent - amount)
    project.save(update_fields=['stars_spent'])


def reserve(user, amount: int, project: StudioProject) -> bool:
    """Lock estimated stars from user's balance into project.stars_reserved."""
    user.refresh_from_db(fields=['pages_count'])
    if user.pages_count < amount:
        return False
    user.spend_pages(amount)
    project.stars_reserved += amount
    project.save(update_fields=['stars_reserved'])
    return True


def charge_from_reserve(amount: int, project: StudioProject) -> bool:
    """Spend from reserve first; top up from live balance if reserve is short."""
    take = min(amount, project.stars_reserved)
    project.stars_reserved -= take
    project.stars_spent += take
    rest = amount - take
    if rest > 0:
        user = project.user
        user.refresh_from_db(fields=['pages_count'])
        if user.pages_count < rest:
            project.save(update_fields=['stars_reserved', 'stars_spent'])
            return False
        user.spend_pages(rest)
        project.stars_spent += rest
    project.save(update_fields=['stars_reserved', 'stars_spent'])
    return True


def release_reserve(project: StudioProject):
    """Return unused reserved stars to the user's balance."""
    if project.stars_reserved > 0:
        project.user.add_pages(project.stars_reserved)
        project.stars_reserved = 0
        project.save(update_fields=['stars_reserved'])
