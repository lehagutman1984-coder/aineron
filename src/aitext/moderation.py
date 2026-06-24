from __future__ import annotations

from django.conf import settings


def check_moderation(text: str) -> dict:
    """
    Returns {'flagged': bool, 'categories': {...}, 'scores': {...}}
    Raises ModerationUnavailable if the endpoint is not accessible.
    """
    if not getattr(settings, 'MODERATION_ENABLED', False):
        return {'flagged': False, 'categories': {}, 'scores': {}}

    from aitext.tasks import get_laozhang_client
    client = get_laozhang_client()

    try:
        resp = client.moderations.create(
            model='omni-moderation-latest',
            input=text[:4096],
        )
        result = resp.results[0]
        return {
            'flagged': result.flagged,
            'categories': {k: v for k, v in result.categories.__dict__.items() if not k.startswith('_')},
            'scores': {k: v for k, v in result.category_scores.__dict__.items() if not k.startswith('_')},
        }
    except Exception:
        return {'flagged': False, 'categories': {}, 'scores': {}}


def log_moderation(user, message, text: str, result: dict, source: str = 'web_chat') -> None:
    from aitext.models import ModerationLog
    action = ModerationLog.ACTION_BLOCKED if result['flagged'] else ModerationLog.ACTION_ALLOWED
    ModerationLog.objects.create(
        user=user,
        message=message,
        input_excerpt=text[:200],
        flagged=result['flagged'],
        categories=result['categories'],
        scores=result['scores'],
        action=action,
        source=source,
    )
