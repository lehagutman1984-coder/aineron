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


def spawn_sandbox(project_id: str) -> str:
    """Creates container on bridge network (internet available). Returns container_id."""
    client = get_docker()
    container = client.containers.run(
        settings.STUDIO_SANDBOX_IMAGE,
        command='sleep infinity',
        detach=True,
        name=f'sandbox_{project_id[:8]}',
        mem_limit=settings.STUDIO_SANDBOX_MEM,
        nano_cpus=int(settings.STUDIO_SANDBOX_CPUS * 1e9),
        pids_limit=256,
        cap_drop=['ALL'],
        security_opt=['no-new-privileges'],
        network_mode='bridge',
        labels={'studio_project': project_id},
    )
    return container.id


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


def start_dev_server(container_id: str) -> int:
    exec_command(container_id, 'nohup pnpm dev --port 3000 --host 0.0.0.0 > /tmp/dev.log 2>&1 &')
    return 3000


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
