import base64
import requests
from django.conf import settings


def _api(path):
    return f"{settings.STUDIO_GITEA_URL}/api/v1{path}"


def _headers():
    return {
        'Authorization': f'token {settings.STUDIO_GITEA_ADMIN_TOKEN}',
        'Content-Type': 'application/json',
    }


def create_user(username, email, password) -> dict:
    r = requests.post(_api('/admin/users'), headers=_headers(), json={
        'username': username,
        'email': email,
        'password': password,
        'must_change_password': False,
        'send_notify': False,
    })
    return r.json()


def create_repo(username, repo, private=True) -> dict:
    r = requests.post(_api(f'/admin/users/{username}/repos'), headers=_headers(), json={
        'name': repo,
        'private': private,
        'auto_init': True,
        'default_branch': 'main',
    })
    return r.json()


def put_file(owner, repo, path, content, message, branch='main') -> dict:
    """Create or update a file in a Gitea repo. Fetches current sha for updates."""
    enc = base64.b64encode(content.encode()).decode()
    url = _api(f'/repos/{owner}/{repo}/contents/{path}')
    get = requests.get(url, headers=_headers(), params={'ref': branch})
    payload = {'content': enc, 'message': message, 'branch': branch}
    if get.status_code == 200:
        payload['sha'] = get.json().get('sha')
        r = requests.put(url, headers=_headers(), json=payload)
    else:
        r = requests.post(url, headers=_headers(), json=payload)
    return r.json()


def get_commits(owner, repo, limit=20) -> list:
    r = requests.get(
        _api(f'/repos/{owner}/{repo}/commits'),
        headers=_headers(),
        params={'limit': limit},
    )
    return r.json() if r.status_code == 200 else []


def put_files_batch(owner, repo, files: dict, message: str, branch: str = 'main') -> dict:
    """Commit multiple files atomically in a single Gitea commit."""
    ops = []
    for path, content in files.items():
        url = _api(f'/repos/{owner}/{repo}/contents/{path}')
        get = requests.get(url, headers=_headers(), params={'ref': branch})
        op = {
            'operation': 'update' if get.status_code == 200 else 'create',
            'path': path,
            'content': base64.b64encode(content.encode()).decode(),
        }
        if get.status_code == 200:
            op['sha'] = get.json().get('sha')
        ops.append(op)
    r = requests.post(
        _api(f'/repos/{owner}/{repo}/contents'),
        headers=_headers(),
        json={'files': ops, 'message': message, 'branch': branch},
    )
    return r.json()


def list_tree(owner: str, repo: str, branch: str = 'main', path: str = '', token: str | None = None) -> list:
    """Returns flat list of tree items for external Gitea repos.

    token: personal access token (for external repos). If None, uses admin token.
    """
    hdrs = {'Authorization': f'token {token}'} if token else _headers()
    # Use Gitea git/trees API for recursive listing
    r = requests.get(
        _api(f'/repos/{owner}/{repo}/git/trees/{branch}'),
        headers=hdrs,
        params={'recursive': True},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    items = []
    for item in r.json().get('tree', []):
        if path and not item['path'].startswith(path):
            continue
        items.append({
            'path': item['path'],
            'type': 'dir' if item['type'] == 'tree' else 'file',
            'size': item.get('size'),
        })
    return items


def get_file_content_ext(owner: str, repo: str, path: str, branch: str = 'main', token: str | None = None) -> str:
    """Fetch file from external Gitea repo using personal access token."""
    hdrs = {'Authorization': f'token {token}'} if token else _headers()
    r = requests.get(
        _api(f'/repos/{owner}/{repo}/contents/{path}'),
        headers=hdrs,
        params={'ref': branch},
        timeout=15,
    )
    if r.status_code == 200:
        return base64.b64decode(r.json()['content']).decode('utf-8', errors='replace')
    return ''


def push_files_ext(owner: str, repo: str, files: list, message: str, branch: str = 'main', token: str | None = None) -> dict:
    """Push multiple files to external Gitea repo.

    files: [{"path": "...", "content": "..."}, ...]
    """
    hdrs = {'Authorization': f'token {token}', 'Content-Type': 'application/json'} if token else _headers()
    ops = []
    for f in files:
        path = f['path']
        content_b64 = base64.b64encode(f['content'].encode('utf-8')).decode()
        get_r = requests.get(
            _api(f'/repos/{owner}/{repo}/contents/{path}'),
            headers=hdrs,
            params={'ref': branch},
            timeout=10,
        )
        op = {
            'operation': 'update' if get_r.status_code == 200 else 'create',
            'path': path,
            'content': content_b64,
        }
        if get_r.status_code == 200:
            op['sha'] = get_r.json().get('sha')
        ops.append(op)
    r = requests.post(
        _api(f'/repos/{owner}/{repo}/contents'),
        headers=hdrs,
        json={'files': ops, 'message': message, 'branch': branch},
        timeout=30,
    )
    if r.status_code in (200, 201):
        return {'pushed': len(files), 'errors': []}
    return {'pushed': 0, 'errors': [{'path': '*', 'error': r.text[:200]}]}


def get_file_content(owner, repo, path, ref='main') -> str:
    r = requests.get(
        _api(f'/repos/{owner}/{repo}/contents/{path}'),
        headers=_headers(),
        params={'ref': ref},
    )
    if r.status_code == 200:
        return base64.b64decode(r.json()['content']).decode()
    return ''
