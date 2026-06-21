import base64
import requests


def _headers(token: str) -> dict:
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def list_tree(owner: str, repo: str, token: str, branch: str = 'main', path: str = '') -> list:
    """Returns flat list of tree items: [{path, type('blob'|'tree'), size?}, ...]"""
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}'
    r = requests.get(url, headers=_headers(token), params={'recursive': '1'}, timeout=15)
    r.raise_for_status()
    data = r.json()
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


def get_file_content(owner: str, repo: str, token: str, path: str, ref: str = 'main') -> str:
    """Fetch file content (decoded from base64)."""
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
    r = requests.get(url, headers=_headers(token), params={'ref': ref}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return base64.b64decode(data['content']).decode('utf-8', errors='replace')


def _get_file_sha(owner: str, repo: str, token: str, path: str, branch: str) -> str | None:
    url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
    r = requests.get(url, headers=_headers(token), params={'ref': branch}, timeout=10)
    if r.status_code == 200:
        return r.json().get('sha')
    return None


def push_files(owner: str, repo: str, token: str, files: list, message: str, branch: str = 'main') -> dict:
    """Push multiple files via individual Contents API calls.

    files: [{"path": "...", "content": "..."}, ...]
    Returns: {"pushed": N, "errors": [...]}
    """
    pushed = 0
    errors = []
    for f in files:
        path = f['path']
        content_b64 = base64.b64encode(f['content'].encode('utf-8')).decode()
        sha = _get_file_sha(owner, repo, token, path, branch)
        payload = {
            'message': message,
            'content': content_b64,
            'branch': branch,
        }
        if sha:
            payload['sha'] = sha

        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{path}'
        r = requests.put(url, headers=_headers(token), json=payload, timeout=20)
        if r.status_code in (200, 201):
            pushed += 1
        else:
            errors.append({'path': path, 'error': r.text[:200]})
    return {'pushed': pushed, 'errors': errors}
