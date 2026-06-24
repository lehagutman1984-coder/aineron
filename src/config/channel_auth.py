from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore


@database_sync_to_async
def get_user_from_session(session_key):
    from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY
    from django.contrib.auth import get_user_model
    try:
        session = SessionStore(session_key)
        uid = session.get(SESSION_KEY)
        backend_path = session.get(BACKEND_SESSION_KEY)
        if uid and backend_path:
            User = get_user_model()
            return User.objects.get(pk=uid)
    except Exception:
        pass
    return AnonymousUser()


class SessionAuthMiddleware(BaseMiddleware):
    """Authenticates WebSocket connections via Django session cookie."""

    async def __call__(self, scope, receive, send):
        cookies_raw = dict(scope.get('headers', [])).get(b'cookie', b'').decode()
        cookies = {}
        for part in cookies_raw.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                cookies[k.strip()] = v.strip()

        session_key = cookies.get('sessionid')
        scope['user'] = await get_user_from_session(session_key) if session_key else AnonymousUser()
        return await super().__call__(scope, receive, send)


def SessionAuthMiddlewareStack(inner):
    return SessionAuthMiddleware(inner)
