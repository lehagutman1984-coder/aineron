import io
import tarfile
import logging
import docker
from django.conf import settings

logger = logging.getLogger('studio.sandbox')
_docker = None


def get_docker():
    global _docker
    if _docker is None:
        _docker = docker.from_env()
    return _docker


def count_user_sandboxes(user_id) -> int:
    """Count running containers owned by a user (by Docker label)."""
    client = get_docker()
    return len(client.containers.list(filters={'label': f'studio_user={user_id}'}))


def spawn_sandbox(project_id: str, user_id=None) -> str:
    """Creates container on bridge network (internet available). Returns container name (DNS-resolvable)."""
    client = get_docker()
    name = f'sandbox_{project_id[:8]}'
    try:
        client.containers.get(name).remove(force=True)
    except docker.errors.NotFound:
        pass
    labels = {'studio_project': project_id}
    if user_id is not None:
        labels['studio_user'] = str(user_id)
    container = client.containers.run(
        settings.STUDIO_SANDBOX_IMAGE,
        command='sleep infinity',
        detach=True,
        name=name,
        mem_limit=settings.STUDIO_SANDBOX_MEM,
        nano_cpus=int(settings.STUDIO_SANDBOX_CPUS * 1e9),
        pids_limit=256,
        cap_drop=['ALL'],
        security_opt=['no-new-privileges'],
        network_mode='bridge',
        dns=['8.8.8.8', '8.8.4.4'],
        labels=labels,
    )
    return container.name


def write_files(container_id: str, files: dict):
    """files: {path: content}. Writes as tar archive to /workspace."""
    client = get_docker()
    container = client.containers.get(container_id)
    stream = io.BytesIO()
    tar = tarfile.open(fileobj=stream, mode='w')
    for path, content in files.items():
        data = content.encode('utf-8')
        info = tarfile.TarInfo(name=path.lstrip('/'))
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tar.close()
    stream.seek(0)
    container.put_archive('/workspace', stream.read())


def exec_command(container_id: str, cmd: str, workdir='/workspace') -> tuple:
    """Returns (exit_code, output_str)."""
    client = get_docker()
    container = client.containers.get(container_id)
    result = container.exec_run(['sh', '-lc', cmd], workdir=workdir, demux=False)
    out = result.output.decode('utf-8', errors='replace') if result.output else ''
    return result.exit_code, out


def install_deps(container_id: str) -> tuple:
    """pnpm install on bridge network (before isolation)."""
    return exec_command(container_id, 'pnpm install --prefer-offline=false')


def isolate(container_id: str):
    """Disconnects from bridge, connects to internal sandbox_net."""
    client = get_docker()
    container = client.containers.get(container_id)
    try:
        client.networks.get('bridge').disconnect(container)
    except Exception:
        pass
    client.networks.get(settings.STUDIO_SANDBOX_NET).connect(container)


def sync_all(project) -> None:
    """Write all StudioFile objects for a project into the sandbox container."""
    cid = project.sandbox_container_id
    if not cid:
        return
    files = {f.path: f.content for f in project.files.all()}
    if files:
        write_files(cid, files)


def start_dev_server(container_id: str) -> int:
    import json as _json
    client = get_docker()

    _, pkg_raw = exec_command(container_id, 'cat /workspace/package.json 2>/dev/null || echo {}')
    try:
        pkg = _json.loads(pkg_raw)
        scripts = pkg.get('scripts', {})
        has_dev = 'dev' in scripts
        dev_script = scripts.get('dev', '')
        is_next = 'next' in dev_script
    except Exception:
        has_dev = False
        is_next = False

    if has_dev:
        if is_next:
            cmd = ['sh', '-c', 'pnpm dev -- -p 3000 -H 0.0.0.0 > /tmp/dev.log 2>&1']
        else:
            cmd = ['sh', '-c', 'pnpm dev --port 3000 --host 0.0.0.0 > /tmp/dev.log 2>&1']
    else:
        cmd = ['sh', '-c', 'python3 -m http.server 3000 --bind 0.0.0.0 > /tmp/dev.log 2>&1']

    exec_id = client.api.exec_create(container_id, cmd, workdir='/workspace')
    client.api.exec_start(exec_id, detach=True)

    logger.info('sandbox %s: dev server started (has_dev=%s, is_next=%s)', container_id, has_dev, is_next)
    return 3000


def wait_for_ready(container_id: str, timeout: int = 150, warmup: bool = False) -> bool:
    """Poll HTTP server inside container until HTTP 2xx/3xx or timeout.

    warmup=True sends a fire-and-forget request first to trigger Next.js initial compilation.
    """
    import time
    if warmup:
        exec_command(container_id, 'curl -s http://localhost:3000/ > /dev/null 2>&1 || true')
    for i in range(timeout // 3):
        if is_http_alive(container_id):
            logger.info('sandbox %s ready after %ds', container_id, i * 3)
            return True
        time.sleep(3)
    _, log = exec_command(container_id, 'tail -20 /tmp/dev.log 2>/dev/null || true')
    logger.error('sandbox %s not ready after %ds. dev.log: %s', container_id, timeout, log)
    return False


def is_http_alive(container_id: str) -> bool:
    """Quick check: returns True if HTTP server in container answers on :3000."""
    _, out = exec_command(
        container_id,
        'curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ 2>/dev/null || echo 000',
    )
    code = out.strip()[-3:]
    return code.startswith('2') or code.startswith('3')


def run_build_check(container_id: str, is_nextjs: bool = False) -> tuple:
    """Run typecheck/build in container. Returns (exit_code, output)."""
    if is_nextjs:
        return exec_command(container_id, 'pnpm build 2>&1 | tail -n 150')
    return exec_command(
        container_id,
        'pnpm -s exec tsc --noEmit 2>&1 | tail -n 100 || pnpm -s build 2>&1 | tail -n 120',
    )


def get_logs_stream(container_id: str):
    code, out = exec_command(container_id, 'cat /tmp/dev.log || true')
    for line in out.splitlines():
        yield line


def kill_sandbox(container_id: str):
    client = get_docker()
    try:
        client.containers.get(container_id).remove(force=True)
    except docker.errors.NotFound:
        pass
