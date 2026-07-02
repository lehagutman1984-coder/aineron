import tiktoken
from .models import StudioProject
from .models_catalog import MODEL_TIER
from core.money import apply_min_charge

# Копеек за 1000 токенов (было STAR_RATE {fast:1, coder:1.7, smart:3} × 100 — тот же множитель).
KOPECK_RATE = {'fast': 100, 'coder': 170, 'smart': 300}

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


def estimate_kopecks(project: StudioProject, planned_steps: int = 5) -> int:
    """Estimate total kopecks for 3-role pipeline: architect(1x) + coder+guardian(N steps)."""
    idata = getattr(project, 'interview_data', {}) or {}
    plan = idata.get('plan')
    if isinstance(plan, list) and plan:
        planned_steps = len(plan)
    elif idata.get('planned_steps'):
        planned_steps = int(idata['planned_steps'])
    total = 0.0
    ai_tier = MODEL_TIER.get(getattr(project, 'ai_model', ''), 'fast')
    agent_models = getattr(project, 'agent_models', {}) or {}

    def tier_for(name, default_tier):
        m = agent_models.get(name)
        return MODEL_TIER.get(m, default_tier) if m else (ai_tier if name == 'coder' else default_tier)

    arch_tier, arch_budget = AGENT_BUDGET['architect']
    total += (arch_budget / 1000.0) * KOPECK_RATE.get(tier_for('architect', arch_tier), KOPECK_RATE['smart'])

    coder_tier, coder_budget = AGENT_BUDGET['coder']
    total += (coder_budget / 1000.0) * KOPECK_RATE.get(tier_for('coder', coder_tier), KOPECK_RATE['fast']) * planned_steps

    guardian_tier, guardian_budget = AGENT_BUDGET['guardian']
    total += (guardian_budget / 1000.0) * KOPECK_RATE.get(tier_for('guardian', guardian_tier), KOPECK_RATE['smart']) * planned_steps

    return int(total) + 100  # +1 ₽ буфер на округления


def kopecks_for_tokens(prompt_tokens: int, completion_tokens: int, tier: str) -> int:
    """Реальная стоимость одного вызова агента по факту токенов (суммарные prompt+completion)."""
    total = (prompt_tokens or 0) + (completion_tokens or 0)
    rate = KOPECK_RATE.get(tier, KOPECK_RATE['fast'])
    raw = int((total / 1000.0) * rate)
    return apply_min_charge(raw)


def coder_tier_for_model(model: str) -> str:
    """Return billing tier based on model id used by CoderAgent."""
    return MODEL_TIER.get(model, 'fast')


def can_afford(user, amount_kopecks: int) -> bool:
    return user.balance_kopecks >= amount_kopecks


def charge(user, amount_kopecks: int, project: StudioProject, reference: str = ''):
    user.spend_kopecks(amount_kopecks, type='spend', reference=reference)
    from django.db.models import F
    StudioProject.objects.filter(pk=project.pk).update(
        stars_spent_kopecks=F('stars_spent_kopecks') + amount_kopecks,
        stars_spent=F('stars_spent') + max(0, amount_kopecks // 100),
    )
    project.refresh_from_db(fields=['stars_spent_kopecks', 'stars_spent'])


def refund(user, amount_kopecks: int, project: StudioProject, reference: str = ''):
    user.add_kopecks(amount_kopecks, type='refund', reference=reference)
    from django.db.models import F
    from django.db.models.functions import Greatest
    StudioProject.objects.filter(pk=project.pk).update(
        stars_spent_kopecks=Greatest(F('stars_spent_kopecks') - amount_kopecks, 0),
        stars_spent=Greatest(F('stars_spent') - max(0, amount_kopecks // 100), 0),
    )
    project.refresh_from_db(fields=['stars_spent_kopecks', 'stars_spent'])


def reserve(user, amount_kopecks: int, project: StudioProject, reference: str = '') -> bool:
    """Lock estimated kopecks from user's balance into project.stars_reserved_kopecks."""
    user.refresh_from_db(fields=['balance_kopecks'])
    if not user.has_enough_kopecks(amount_kopecks):
        return False
    # Дубликат reference (ретрай/повторный запуск): spend_kopecks вернёт True,
    # НЕ списав баланс. Инкрементировать резерв в этом случае нельзя — иначе
    # появляется фантомный резерв, который release_reserve потом реально начислит.
    already_spent = False
    if reference:
        from users.models import BalanceTransaction
        already_spent = BalanceTransaction.objects.filter(
            user=user, type='spend', reference=reference,
        ).exists()
    ok = user.spend_kopecks(amount_kopecks, type='spend', reference=reference)
    if not ok:
        return False
    if already_spent:
        return True
    from django.db.models import F
    StudioProject.objects.filter(pk=project.pk).update(
        stars_reserved_kopecks=F('stars_reserved_kopecks') + amount_kopecks,
        stars_reserved=F('stars_reserved') + max(0, amount_kopecks // 100),
    )
    project.refresh_from_db(fields=['stars_reserved_kopecks', 'stars_reserved'])
    return True


def charge_from_reserve(amount_kopecks: int, project: StudioProject, reference: str = '') -> bool:
    """
    Spend from reserve first; top up from live balance if reserve is short.
    reference (если задан) обеспечивает идемпотентность по (type, reference) —
    важно передавать уникальный на (project, agent, step) ключ, а не саму сумму,
    иначе два РАЗНЫХ события с одинаковой стоимостью ошибочно схлопнутся в одно.
    """
    from django.db.models import F
    from django.db.models.functions import Greatest

    project.refresh_from_db(fields=['stars_reserved_kopecks', 'stars_spent_kopecks'])
    take = min(amount_kopecks, project.stars_reserved_kopecks)
    rest = amount_kopecks - take

    if rest > 0:
        user = project.user
        user.refresh_from_db(fields=['balance_kopecks'])
        if not user.has_enough_kopecks(rest):
            return False
        if not user.spend_kopecks(rest, type='spend', reference=reference):
            return False

    StudioProject.objects.filter(pk=project.pk).update(
        stars_reserved_kopecks=Greatest(F('stars_reserved_kopecks') - take, 0),
        stars_reserved=Greatest(F('stars_reserved') - max(0, take // 100), 0),
        stars_spent_kopecks=F('stars_spent_kopecks') + amount_kopecks,
        stars_spent=F('stars_spent') + max(0, amount_kopecks // 100),
    )
    project.refresh_from_db(fields=['stars_reserved_kopecks', 'stars_reserved', 'stars_spent_kopecks', 'stars_spent'])
    return True


def release_reserve(project: StudioProject, reference: str = ''):
    """Return unused reserved kopecks to the user's balance."""
    project.refresh_from_db(fields=['stars_reserved_kopecks'])
    if project.stars_reserved_kopecks > 0:
        amount = project.stars_reserved_kopecks
        project.user.add_kopecks(amount, type='refund', reference=reference)
        StudioProject.objects.filter(pk=project.pk).update(stars_reserved_kopecks=0, stars_reserved=0)
        project.refresh_from_db(fields=['stars_reserved_kopecks', 'stars_reserved'])


def release_reserve_amount(project: StudioProject, amount_kopecks: int, reference: str = ''):
    """
    Частичный возврат резерва (остаток превью-сессии и т.п.), не затрагивая
    резерв параллельно идущего пайплайна. Клэмпится к текущему резерву.
    """
    from django.db.models import F
    from django.db.models.functions import Greatest

    project.refresh_from_db(fields=['stars_reserved_kopecks'])
    amount = min(amount_kopecks, project.stars_reserved_kopecks)
    if amount <= 0:
        return
    project.user.add_kopecks(amount, type='refund', reference=reference)
    StudioProject.objects.filter(pk=project.pk).update(
        stars_reserved_kopecks=Greatest(F('stars_reserved_kopecks') - amount, 0),
        stars_reserved=Greatest(F('stars_reserved') - max(0, amount // 100), 0),
    )
    project.refresh_from_db(fields=['stars_reserved_kopecks', 'stars_reserved'])
