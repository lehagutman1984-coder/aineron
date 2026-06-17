import tiktoken
from .models import StudioProject
from .models_catalog import MODEL_TIER

STAR_RATE = {'fast': 1, 'coder': 1.7, 'smart': 3}

AGENT_BUDGET = {
    # 3-role pipeline
    'architect': ('smart', 10000),   # opus, one time — PROJECT.md + COMMITS.md
    'coder':     ('coder', 12000),   # qwen3-coder-plus, per step
    'guardian':  ('smart', 6000),    # sonnet, per step — review+test+fixplan
    # Legacy agents kept for backward compat with old in-flight projects
    'interviewer': ('fast', 2000),
    'analyst':     ('smart', 6000),
    'planner':     ('smart', 8000),
    'reviewer':    ('smart', 6000),
    'tester':      ('fast', 4000),
    'fixer':       ('smart', 5000),
}


def count_tokens(text: str, model: str = 'gpt-4') -> int:
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding('cl100k_base')
    return len(enc.encode(text or ''))


def estimate_stars(project: StudioProject, planned_steps: int = 5) -> int:
    """Estimate total stars for 3-role pipeline: architect(1x) + coder+guardian(N steps)."""
    total = 0.0
    ai_tier = MODEL_TIER.get(getattr(project, 'ai_model', ''), 'fast')
    agent_models = getattr(project, 'agent_models', {}) or {}

    def tier_for(name, default_tier):
        m = agent_models.get(name)
        return MODEL_TIER.get(m, default_tier) if m else (ai_tier if name == 'coder' else default_tier)

    arch_tier, arch_budget = AGENT_BUDGET['architect']
    total += (arch_budget / 1000.0) * STAR_RATE.get(tier_for('architect', arch_tier), STAR_RATE['smart'])

    coder_tier, coder_budget = AGENT_BUDGET['coder']
    total += (coder_budget / 1000.0) * STAR_RATE.get(tier_for('coder', coder_tier), STAR_RATE['fast']) * planned_steps

    guardian_tier, guardian_budget = AGENT_BUDGET['guardian']
    total += (guardian_budget / 1000.0) * STAR_RATE.get(tier_for('guardian', guardian_tier), STAR_RATE['smart']) * planned_steps

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
