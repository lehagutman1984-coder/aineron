import base64
import requests


def _headers(token: str) -> dict:
    return {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def list_tree(owner: str, repo: str, token: str, branch: str = 'main', path: str = '') -> list:
    """Returns flat list of tree items: [{path, type('file'|'dir'), size?}, ...]"""
    url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}'
    r = requests.get(url, headers=_headers(token), params={'recursive': '1'}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get('truncated'):
        import logging
        logging.getLogger(__name__).warning('GitHub tree truncated for %s/%s — showing partial results', owner, repo)
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


def push_files(owner: str, repo: str, token: str, files: list, message: str, branch: str = 'main') -> dict:
    """Push multiple files as a single atomic commit using GitHub Git Data API.

    files: [{"path": "...", "content": "..."}, ...]
    Returns: {"pushed": N, "errors": [...], "sha": "commit_sha"}
    """
    hdrs = _headers(token)
    base = f'https://api.github.com/repos/{owner}/{repo}'

    try:
        # 1. Get current branch HEAD
        r = requests.get(f'{base}/branches/{branch}', headers=hdrs, timeout=10)
        r.raise_for_status()
        branch_data = r.json()
        base_commit_sha = branch_data['commit']['sha']
        base_tree_sha = branch_data['commit']['commit']['tree']['sha']

        # 2. Create blobs for each file
        tree_entries = []
        for f in files:
            r = requests.post(
                f'{base}/git/blobs',
                headers=hdrs,
                json={'content': f['content'], 'encoding': 'utf-8'},
                timeout=20,
            )
            r.raise_for_status()
            tree_entries.append({
                'path': f['path'],
                'mode': '100644',
                'type': 'blob',
                'sha': r.json()['sha'],
            })

        # 3. Create tree
        r = requests.post(
            f'{base}/git/trees',
            headers=hdrs,
            json={'base_tree': base_tree_sha, 'tree': tree_entries},
            timeout=20,
        )
        r.raise_for_status()
        new_tree_sha = r.json()['sha']

        # 4. Create commit
        r = requests.post(
            f'{base}/git/commits',
            headers=hdrs,
            json={'message': message, 'tree': new_tree_sha, 'parents': [base_commit_sha]},
            timeout=20,
        )
        r.raise_for_status()
        new_commit_sha = r.json()['sha']

        # 5. Update branch reference
        r = requests.patch(
            f'{base}/git/refs/heads/{branch}',
            headers=hdrs,
            json={'sha': new_commit_sha},
            timeout=20,
        )
        r.raise_for_status()

        return {'pushed': len(files), 'errors': [], 'sha': new_commit_sha}

    except requests.HTTPError as e:
        return {'pushed': 0, 'errors': [{'path': '*', 'error': f'{e.response.status_code}: {e.response.text[:200]}'}]}
    except Exception as e:
        return {'pushed': 0, 'errors': [{'path': '*', 'error': str(e)[:200]}]}


def create_branch(owner: str, repo: str, token: str, new_branch: str, from_branch: str = 'main') -> str:
    """Create a new branch from from_branch. Returns the SHA of the new branch head."""
    hdrs = _headers(token)
    base = f'https://api.github.com/repos/{owner}/{repo}'

    r = requests.get(f'{base}/branches/{from_branch}', headers=hdrs, timeout=10)
    r.raise_for_status()
    sha = r.json()['commit']['sha']

    r = requests.post(
        f'{base}/git/refs',
        headers=hdrs,
        json={'ref': f'refs/heads/{new_branch}', 'sha': sha},
        timeout=10,
    )
    if r.status_code == 422:
        # Branch already exists — OK, reuse it
        pass
    else:
        r.raise_for_status()
    return sha


def create_pull(owner: str, repo: str, token: str, title: str, body: str,
                head: str, base: str) -> str:
    """Create a pull request. Returns the PR URL."""
    hdrs = _headers(token)
    r = requests.post(
        f'https://api.github.com/repos/{owner}/{repo}/pulls',
        headers=hdrs,
        json={'title': title, 'body': body, 'head': head, 'base': base},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()['html_url']
