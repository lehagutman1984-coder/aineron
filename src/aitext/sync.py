"""
Sprint 4.2 — Inbound sync: репозиторий → база знаний проекта.

Точки входа:
  sync_connector(connector_id) — полная инкрементальная синхронизация файлов

Поддерживаемые расширения: SYNC_EXTENSIONS (мн-во строк).
Лимит файла: SYNC_MAX_BYTES (1 MB).
"""

import base64
import logging
import os

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Только текстовые форматы — бинарные файлы не приносят пользы в базе знаний
SYNC_EXTENSIONS = {
    '.md', '.txt', '.rst', '.csv',
    '.py', '.js', '.ts', '.tsx', '.jsx',
    '.html', '.css', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.sh', '.sql', '.xml',
}
SYNC_MAX_BYTES = 1 * 1024 * 1024   # 1 MB per file
SYNC_MAX_FILES = 50                 # дефолт; переопределяется через PROJECT_SYNC_MAX_FILES в settings


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _github_headers(token: str) -> dict:
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _github_tree(connector, token: str) -> list[dict]:
    """Returns [{path, sha, size}, ...] for all blobs in the tree."""
    url = f'https://api.github.com/repos/{connector.owner}/{connector.repo}/git/trees/{connector.branch}'
    r = requests.get(url, headers=_github_headers(token), params={'recursive': '1'}, timeout=20)
    r.raise_for_status()
    data = r.json()

    if data.get('truncated'):
        # GitHub обрезал recursive tree — получаем каждую поддиректорию отдельно
        logger.warning('[sync] GitHub tree truncated — fetching subtrees individually')
        return _github_tree_full(connector, token)

    result = []
    for item in data.get('tree', []):
        if item.get('type') != 'blob':
            continue
        ext = os.path.splitext(item['path'])[1].lower()
        if ext not in SYNC_EXTENSIONS:
            continue
        size = item.get('size', 0) or 0
        if size > SYNC_MAX_BYTES:
            continue
        result.append({'path': item['path'], 'sha': item['sha'], 'size': size})
    return result[:int(getattr(settings, 'PROJECT_SYNC_MAX_FILES', SYNC_MAX_FILES))]


def _github_tree_full(connector, token: str) -> list[dict]:
    """Обходит дерево репозитория по уровням когда recursive tree truncated."""
    max_files = int(getattr(settings, 'PROJECT_SYNC_MAX_FILES', SYNC_MAX_FILES))
    result = []
    # Получаем корневое дерево (без recursive)
    root_url = f'https://api.github.com/repos/{connector.owner}/{connector.repo}/git/trees/{connector.branch}'
    root_r = requests.get(root_url, headers=_github_headers(token), timeout=20)
    root_r.raise_for_status()
    queue = [item for item in root_r.json().get('tree', []) if item.get('type') in ('blob', 'tree')]

    visited_trees = set()
    while queue and len(result) < max_files:
        item = queue.pop(0)
        if item.get('type') == 'blob':
            ext = os.path.splitext(item['path'])[1].lower()
            size = item.get('size', 0) or 0
            if ext in SYNC_EXTENSIONS and size <= SYNC_MAX_BYTES:
                result.append({'path': item['path'], 'sha': item['sha'], 'size': size})
        elif item.get('type') == 'tree' and item['sha'] not in visited_trees:
            visited_trees.add(item['sha'])
            try:
                sub_url = f'https://api.github.com/repos/{connector.owner}/{connector.repo}/git/trees/{item["sha"]}'
                sub_r = requests.get(sub_url, headers=_github_headers(token), timeout=15)
                sub_r.raise_for_status()
                prefix = item['path'] + '/'
                for sub in sub_r.json().get('tree', []):
                    sub['path'] = prefix + sub['path']
                    queue.append(sub)
            except Exception as e:
                logger.warning(f'[sync] failed to fetch subtree {item["path"]}: {e}')

    logger.info(f'[sync] full tree walk: {len(result)} files found')
    return result[:max_files]


def _github_file(connector, token: str, path: str) -> str:
    url = f'https://api.github.com/repos/{connector.owner}/{connector.repo}/contents/{path}'
    r = requests.get(url, headers=_github_headers(token), params={'ref': connector.branch}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return base64.b64decode(data['content']).decode('utf-8', errors='replace')


# ── Gitea helpers ──────────────────────────────────────────────────────────────

def _gitea_base(connector) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(connector.repo_url)
    return f'{parsed.scheme}://{parsed.netloc}' if parsed.netloc else getattr(settings, 'STUDIO_GITEA_URL', 'http://gitea:3000')


def _gitea_headers(token: str) -> dict:
    return {'Authorization': f'token {token}', 'Content-Type': 'application/json'}


def _gitea_tree(connector, token: str) -> list[dict]:
    base = _gitea_base(connector)
    url = f'{base}/api/v1/repos/{connector.owner}/{connector.repo}/git/trees/{connector.branch}'
    r = requests.get(url, headers=_gitea_headers(token), params={'recursive': 'true', 'token': ''}, timeout=20)
    r.raise_for_status()
    data = r.json()
    result = []
    for item in data.get('tree', []):
        if item.get('type') != 'blob':
            continue
        ext = os.path.splitext(item.get('path', ''))[1].lower()
        if ext not in SYNC_EXTENSIONS:
            continue
        size = item.get('size', 0) or 0
        if size > SYNC_MAX_BYTES:
            continue
        result.append({'path': item['path'], 'sha': item['sha'], 'size': size})
    return result[:int(getattr(settings, 'PROJECT_SYNC_MAX_FILES', SYNC_MAX_FILES))]


def _gitea_file(connector, token: str, path: str) -> str:
    base = _gitea_base(connector)
    url = f'{base}/api/v1/repos/{connector.owner}/{connector.repo}/contents/{path}'
    r = requests.get(url, headers=_gitea_headers(token), params={'ref': connector.branch}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return base64.b64decode(data.get('content', '')).decode('utf-8', errors='replace')


# ── Core sync ──────────────────────────────────────────────────────────────────

def _detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return 'pdf'
    if ext in {'.doc', '.docx', '.odt', '.rtf'}:
        return 'doc'
    if ext in {'.txt', '.md', '.rst', '.csv'}:
        return 'text'
    if ext in {'.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json',
               '.yaml', '.yml', '.toml', '.ini', '.sh', '.sql', '.xml'}:
        return 'code'
    return 'other'


VERSION_RETENTION = 10  # Макс. версий на файл


def _create_version_snapshot(pf, old_text: str):
    """Sprint 5.4: создаёт снапшот версии файла. Удаляет лишние (старше VERSION_RETENTION)."""
    if not getattr(settings, 'PROJECT_FILE_VERSIONS', False):
        return
    if not old_text:
        return
    try:
        from aitext.models import ProjectFileVersion
        ProjectFileVersion.objects.create(
            file=pf,
            content_snapshot=old_text,
            repo_sha=pf.repo_sha,
        )
        # Ретеншн: удалить версии старше VERSION_RETENTION
        old_ids = list(
            ProjectFileVersion.objects.filter(file=pf)
            .order_by('-created_at')
            .values_list('id', flat=True)[VERSION_RETENTION:]
        )
        if old_ids:
            ProjectFileVersion.objects.filter(id__in=old_ids).delete()
    except Exception as e:
        logger.warning(f'[sync] version snapshot failed for file {pf.id}: {e}')


def sync_connector(connector_id: int) -> dict:
    """Синхронизирует файлы из репозитория в базу знаний проекта.

    Returns {'created': N, 'updated': N, 'deleted': N, 'skipped': N, 'errors': N}
    При PROJECT_FILE_VERSIONS=1 — создаёт снапшоты версий при обновлении.
    """
    from aitext.models import ProjectConnector, ProjectFile
    from aitext.crypto import decrypt_token
    from aitext.tasks import embed_project_file

    try:
        connector = ProjectConnector.objects.select_related('project').get(id=connector_id)
    except ProjectConnector.DoesNotExist:
        logger.error(f'[sync] connector {connector_id} not found')
        return {'error': 'not_found'}

    def _fail(reason: str, exc=None) -> dict:
        report = {'error': reason, 'error_detail': str(exc) if exc else ''}
        connector.sync_status = 'error'
        connector.last_sync_report = report
        connector.last_synced_at = timezone.now()
        connector.save(update_fields=['sync_status', 'last_sync_report', 'last_synced_at'])
        return report

    try:
        token = decrypt_token(connector.access_token_enc)
    except Exception as e:
        logger.error(f'[sync] token decrypt failed for connector {connector_id}: {e}')
        return _fail('token_error', e)

    try:
        if connector.connector_type == 'github':
            remote_tree = _github_tree(connector, token)
        else:
            remote_tree = _gitea_tree(connector, token)
    except Exception as e:
        logger.error(f'[sync] fetch tree failed for connector {connector_id}: {e}')
        return _fail(f'tree_error', e)

    remote_map = {item['path']: item for item in remote_tree}  # path → {path, sha, size}

    # Существующие repo-файлы этого коннектора
    existing_qs = ProjectFile.objects.filter(connector=connector, source='repo')
    existing_map = {pf.repo_path: pf for pf in existing_qs}

    created = updated = deleted = skipped = errors = 0

    # Создаём / обновляем файлы
    for path, remote in remote_map.items():
        existing = existing_map.get(path)
        if existing and existing.repo_sha == remote['sha']:
            skipped += 1
            continue

        try:
            if connector.connector_type == 'github':
                content = _github_file(connector, token, path)
            else:
                content = _gitea_file(connector, token, path)
        except Exception as e:
            logger.warning(f'[sync] failed to fetch {path}: {e}')
            errors += 1
            continue

        filename = os.path.basename(path)
        try:
            if existing:
                # Снапшот старого содержимого перед обновлением
                _create_version_snapshot(existing, existing.extracted_text)
                # Обновляем текст и сбрасываем embed_status
                existing.extracted_text = content
                existing.status = 'ready'
                existing.repo_sha = remote['sha']
                existing.file_size = len(content.encode('utf-8'))
                existing.embed_status = 'none'
                existing.save(update_fields=['extracted_text', 'status', 'repo_sha', 'file_size', 'embed_status'])
                if getattr(settings, 'PROJECT_VECTOR_RAG', False):
                    embed_project_file.delay(existing.id)
                updated += 1
            else:
                pf = ProjectFile.objects.create(
                    project=connector.project,
                    connector=connector,
                    filename=filename,
                    repo_path=path,
                    source='repo',
                    file_size=len(content.encode('utf-8')),
                    file_type=_detect_file_type(filename),
                    extracted_text=content,
                    status='ready',
                    repo_sha=remote['sha'],
                )
                if getattr(settings, 'PROJECT_VECTOR_RAG', False):
                    embed_project_file.delay(pf.id)
                created += 1
        except Exception as e:
            logger.error(f'[sync] failed to save {path}: {e}')
            errors += 1

    # Удаляем файлы, которых больше нет в репозитории
    for path, pf in existing_map.items():
        if path not in remote_map:
            pf.delete()
            deleted += 1

    report = {'created': created, 'updated': updated, 'deleted': deleted, 'skipped': skipped, 'errors': errors}
    connector.last_synced_at = timezone.now()
    connector.sync_status = 'error' if errors > 0 and (created + updated) == 0 else 'ok'
    connector.last_sync_report = report
    connector.save(update_fields=['last_synced_at', 'sync_status', 'last_sync_report'])

    logger.info(
        f'[sync] connector {connector_id} ({connector.owner}/{connector.repo}): '
        f'created={created}, updated={updated}, deleted={deleted}, skipped={skipped}, errors={errors}'
    )
    return report


# ── Polling helpers ────────────────────────────────────────────────────────────

def get_repo_head_sha(connector) -> str | None:
    """Sprint 5.4: получает HEAD SHA ветки (лёгкий запрос без полного синка)."""
    try:
        from aitext.crypto import decrypt_token
        token = decrypt_token(connector.access_token_enc)
    except Exception:
        return None

    try:
        if connector.connector_type == 'github':
            url = f'https://api.github.com/repos/{connector.owner}/{connector.repo}/commits/{connector.branch}'
            r = requests.get(url, headers=_github_headers(token), timeout=10)
            r.raise_for_status()
            return r.json().get('sha', '')
        else:
            base = _gitea_base(connector)
            url = f'{base}/api/v1/repos/{connector.owner}/{connector.repo}/branches/{connector.branch}'
            r = requests.get(url, headers=_gitea_headers(token), timeout=10)
            r.raise_for_status()
            return r.json().get('commit', {}).get('id', '')
    except Exception as e:
        logger.warning(f'[poll] HEAD check failed for connector {connector.id}: {e}')
        return None
