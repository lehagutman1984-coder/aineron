import tiktoken
from .models import StudioProject
from .agents.base import MODEL_SMART

STAR_RATE = {'smart': 3, 'fast': 1}

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
    for agent, (tier, budget) in AGENT_BUDGET.items():
        loops = planned_steps if agent in ('coder', 'reviewer', 'tester') else 1
        toks = budget + (desc_tokens if agent in ('analyst', 'planner') else 0)
        total += (toks / 1000.0) * STAR_RATE[tier] * loops
    return int(total) + 1


def coder_tier_for_model(model: str) -> str:
    """Return billing tier based on model name used by CoderAgent."""
    return 'smart' if model == MODEL_SMART else 'fast'


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
