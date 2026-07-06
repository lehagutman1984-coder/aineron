"""
HTTP-клиент к preview-service (namespace /sandbox/*).

Единственное место, где Django знает про внутренний транспорт. Ретраи — только
на сетевые ошибки идемпотентных вызовов (GET/DELETE); create не ретраится,
чтобы не породить VM-сироту.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT_FAST = 15
_TIMEOUT_SLOW = 90  # create (cold start) и exec (до 300 c своего таймаута — держим соединение)


class PreviewServiceError(Exception):
    """Ошибка транспорта/сервиса. status — HTTP-код ответа сервиса (0 = сеть)."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _base() -> str:
    return getattr(settings, 'PREVIEW_SERVICE_URL', 'http://preview_service:8001').rstrip('/')


def _headers() -> dict:
    return {'X-Internal-Token': getattr(settings, 'PREVIEW_INTERNAL_TOKEN', '')}


def _request(method: str, path: str, json_body=None, params=None,
             timeout=_TIMEOUT_FAST, retries: int = 0):
    url = f'{_base()}{path}'
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.request(
                method, url, json=json_body, params=params,
                headers=_headers(), timeout=timeout,
            )
            if resp.status_code >= 400:
                try:
                    detail = resp.json().get('detail', resp.text)
                except Exception:
                    detail = resp.text
                raise PreviewServiceError(str(detail), status=resp.status_code)
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning('[sandbox] preview-service %s %s network error (try %s): %s',
                           method, path, attempt + 1, exc)
    raise PreviewServiceError(f'preview-service unavailable: {last_exc}', status=0)


def create(session_id: str, template: str, size: str, ttl: int,
           env: dict, user_id: str) -> dict:
    return _request('POST', '/sandbox/create', json_body={
        'session_id': session_id, 'template': template, 'size': size,
        'ttl': ttl, 'env': env or {}, 'user_id': user_id,
    }, timeout=_TIMEOUT_SLOW)


def status(session_id: str) -> dict:
    return _request('GET', f'/sandbox/{session_id}', timeout=_TIMEOUT_FAST, retries=2)


def exec_(session_id: str, payload: dict) -> dict:
    # exec держит соединение до конца команды: таймаут клиента = таймаут команды + запас
    timeout = min(int(payload.get('timeout', 60)), 300) + 30
    return _request('POST', f'/sandbox/{session_id}/exec', json_body=payload, timeout=timeout)


def write_files(session_id: str, files: list) -> dict:
    return _request('POST', f'/sandbox/{session_id}/files',
                    json_body={'files': files}, timeout=_TIMEOUT_SLOW)


def read_file(session_id: str, path: str, op: str = 'read') -> dict:
    return _request('GET', f'/sandbox/{session_id}/files',
                    params={'path': path, 'op': op}, timeout=_TIMEOUT_FAST, retries=1)


def logs(session_id: str, lines: int = 200) -> dict:
    return _request('GET', f'/sandbox/{session_id}/logs',
                    params={'lines': lines}, timeout=_TIMEOUT_FAST, retries=1)


def set_timeout(session_id: str, ttl_seconds: int) -> dict:
    return _request('POST', f'/sandbox/{session_id}/timeout',
                    json_body={'ttl': ttl_seconds}, timeout=_TIMEOUT_FAST)


def kill(session_id: str) -> dict:
    return _request('DELETE', f'/sandbox/{session_id}', timeout=_TIMEOUT_FAST, retries=2)
