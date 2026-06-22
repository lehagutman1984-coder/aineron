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


def _ext_api(base_url: str, path: str) -> str:
    """Build API URL for external Gitea instance."""
    return f"{base_url.rstrip('/')}/api/v1{path}"


def _ext_headers(token: str) -> dict:
    return {'Authorization': f'token {token}', 'Content-Type': 'application/json'}


def list_tree(owner: str, repo: str, branch: str = 'main', path: str = '',
              token: str | None = None, base_url: str | None = None) -> list:
    """Returns flat list of tree items.

    base_url: base URL of external Gitea (e.g. https://gitea.example.com).
              If None, uses internal STUDIO_GITEA_URL with admin token.
    token: personal access token (required when base_url is set).
    """
    if base_url:
        url = _ext_api(base_url, f'/repos/{owner}/{repo}/git/trees/{branch}')
        hdrs = _ext_headers(token) if token else {}
    else:
        url = _api(f'/repos/{owner}/{repo}/git/trees/{branch}')
        hdrs = _headers()

    r = requests.get(url, headers=hdrs, params={'recursive': True}, timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    if data.get('truncated'):
        import logging
        logging.getLogger(__name__).warning('Gitea tree truncated for %s/%s — showing partial results', owner, repo)
    items = []
    for item in data.get('tree', []):
        if path and not item['path'].startswith(path):
            continue
        items.append({
            'path': item['path'],
            'type': 'dir' if item['type'] == 'tree' else 'file',
            'size': item.get('size'),
        })
    return items


def get_file_content_ext(owner: str, repo: str, path: str, branch: str = 'main',
                         token: str | None = None, base_url: str | None = None) -> str:
    """Fetch file from external Gitea repo using personal access token."""
    if base_url:
        url = _ext_api(base_url, f'/repos/{owner}/{repo}/contents/{path}')
        hdrs = _ext_headers(token) if token else {}
    else:
        url = _api(f'/repos/{owner}/{repo}/contents/{path}')
        hdrs = _headers()
    r = requests.get(url, headers=hdrs, params={'ref': branch}, timeout=15)
    if r.status_code == 200:
        return base64.b64decode(r.json()['content']).decode('utf-8', errors='replace')
    return ''


def push_files_ext(owner: str, repo: str, files: list, message: str, branch: str = 'main',
                   token: str | None = None, base_url: str | None = None) -> dict:
    """Push multiple files to external Gitea repo as a single batch commit.

    files: [{"path": "...", "content": "..."}, ...]
    base_url: base URL of external Gitea. If None, uses internal STUDIO_GITEA_URL.
    """
    if base_url:
        hdrs = _ext_headers(token) if token else {}
        api_base = base_url
    else:
        hdrs = _headers()
        api_base = None

    ops = []
    for f in files:
        path = f['path']
        content_b64 = base64.b64encode(f['content'].encode('utf-8')).decode()
        get_url = _ext_api(api_base, f'/repos/{owner}/{repo}/contents/{path}') if api_base else _api(f'/repos/{owner}/{repo}/contents/{path}')
        get_r = requests.get(get_url, headers=hdrs, params={'ref': branch}, timeout=10)
        op = {
            'operation': 'update' if get_r.status_code == 200 else 'create',
            'path': path,
            'content': content_b64,
        }
        if get_r.status_code == 200:
            op['sha'] = get_r.json().get('sha')
        ops.append(op)

    post_url = _ext_api(api_base, f'/repos/{owner}/{repo}/contents') if api_base else _api(f'/repos/{owner}/{repo}/contents')
    r = requests.post(post_url, headers=hdrs, json={'files': ops, 'message': message, 'branch': branch}, timeout=30)
    if r.status_code in (200, 201):
        return {'pushed': len(files), 'errors': []}
    return {'pushed': 0, 'errors': [{'path': '*', 'error': r.text[:200]}]}


def create_branch_ext(owner: str, repo: str, new_branch: str, from_branch: str = 'main',
                      token: str | None = None, base_url: str | None = None) -> None:
    """Create a new branch in external Gitea from from_branch."""
    if base_url:
        hdrs = _ext_headers(token) if token else {}
        api_base = base_url
    else:
        hdrs = _headers()
        api_base = None

    url = _ext_api(api_base, f'/repos/{owner}/{repo}/branches') if api_base else _api(f'/repos/{owner}/{repo}/branches')
    r = requests.post(url, headers=hdrs, json={'new_branch_name': new_branch, 'old_branch_name': from_branch}, timeout=10)
    if r.status_code == 409:
        return  # branch already exists
    r.raise_for_status()


def create_pull_ext(owner: str, repo: str, title: str, body: str, head: str, base: str,
                    token: str | None = None, base_url: str | None = None) -> str:
    """Create a PR in external Gitea. Returns the PR URL."""
    if base_url:
        hdrs = _ext_headers(token) if token else {}
        api_base = base_url
    else:
        hdrs = _headers()
        api_base = None

    url = _ext_api(api_base, f'/repos/{owner}/{repo}/pulls') if api_base else _api(f'/repos/{owner}/{repo}/pulls')
    r = requests.post(url, headers=hdrs, json={
        'title': title, 'body': body, 'head': head, 'base': base,
    }, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get('html_url') or data.get('url', '')


def get_file_content(owner, repo, path, ref='main') -> str:
    r = requests.get(
        _api(f'/repos/{owner}/{repo}/contents/{path}'),
        headers=_headers(),
        params={'ref': ref},
    )
    if r.status_code == 200:
        return base64.b64decode(r.json()['content']).decode()
    return ''
