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


def sync_connector(connector_id: int) -> dict:
    """Синхронизирует файлы из репозитория в базу знаний проекта.

    Returns {'created': N, 'updated': N, 'deleted': N, 'skipped': N}
    """
    from aitext.models import ProjectConnector, ProjectFile
    from aitext.crypto import decrypt_token
    from aitext.tasks import embed_project_file

    try:
        connector = ProjectConnector.objects.select_related('project').get(id=connector_id)
    except ProjectConnector.DoesNotExist:
        logger.error(f'[sync] connector {connector_id} not found')
        return {'error': 'not_found'}

    try:
        token = decrypt_token(connector.access_token_enc)
    except Exception as e:
        logger.error(f'[sync] token decrypt failed for connector {connector_id}: {e}')
        return {'error': 'token_error'}

    try:
        if connector.connector_type == 'github':
            remote_tree = _github_tree(connector, token)
        else:
            remote_tree = _gitea_tree(connector, token)
    except Exception as e:
        logger.error(f'[sync] fetch tree failed for connector {connector_id}: {e}')
        return {'error': f'tree_error: {e}'}

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
        if existing:
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

    # Удаляем файлы, которых больше нет в репозитории
    for path, pf in existing_map.items():
        if path not in remote_map:
            pf.delete()
            deleted += 1

    connector.last_synced_at = timezone.now()
    connector.save(update_fields=['last_synced_at'])

    logger.info(
        f'[sync] connector {connector_id} ({connector.owner}/{connector.repo}): '
        f'created={created}, updated={updated}, deleted={deleted}, skipped={skipped}, errors={errors}'
    )
    return {'created': created, 'updated': updated, 'deleted': deleted, 'skipped': skipped, 'errors': errors}
