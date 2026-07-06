"""Клиент Aineron Sandboxes API."""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "https://aineron.ru/api/v1"
_RETRY_STATUSES = (502, 503, 504)
_RETRIES = 3


class AineronError(Exception):
    """Базовая ошибка SDK."""

    def __init__(self, message: str, code: str = "", status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


class AuthenticationError(AineronError):
    pass


class InsufficientBalanceError(AineronError):
    pass


class RateLimitError(AineronError):
    pass


class SandboxError(AineronError):
    pass


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def _raise_for_error(resp: requests.Response) -> None:
    try:
        error = resp.json().get("error", {})
    except Exception:
        error = {}
    message = error.get("message", f"HTTP {resp.status_code}")
    code = error.get("code", "")
    if resp.status_code in (401, 403):
        raise AuthenticationError(message, code, resp.status_code)
    if resp.status_code == 402:
        raise InsufficientBalanceError(message, code, resp.status_code)
    if resp.status_code == 429:
        raise RateLimitError(message, code, resp.status_code)
    raise SandboxError(message, code, resp.status_code)


class Sandbox:
    """Изолированная microVM для исполнения кода.

    Использование как контекст-менеджер гарантирует остановку (и остановку
    биллинга) даже при исключении внутри блока:

        with Sandbox(template="python", timeout=300) as sbx:
            sbx.write_file("main.py", "print('hi')")
            print(sbx.exec(command="python3 main.py").stdout)
    """

    def __init__(
        self,
        template: str = "base",
        size: str = "standard",
        timeout: int = 300,
        env: dict | None = None,
        metadata: dict | None = None,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        _lazy: bool = False,
    ):
        self._api_key = api_key or os.environ.get("AINERON_API_KEY", "")
        if not self._api_key:
            raise AuthenticationError(
                "API key required: pass api_key= or set AINERON_API_KEY. "
                "Create a key with the 'sandboxes' scope at https://aineron.ru/account/keys/"
            )
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {self._api_key}"
        self.id: str | None = None
        self.public_host: str | None = None
        self.state: str = "new"
        if not _lazy:
            self._create(template, size, timeout, env or {}, metadata or {})

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, retryable: bool = False, **kwargs):
        url = f"{self._base_url}{path}"
        attempts = _RETRIES if retryable else 1
        last = None
        for attempt in range(attempts):
            try:
                resp = self._session.request(method, url, timeout=kwargs.pop("timeout", 330), **kwargs)
            except requests.RequestException as exc:
                last = exc
                if attempt < attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise SandboxError(f"Network error: {exc}") from exc
            if resp.status_code in _RETRY_STATUSES and attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue
            if resp.status_code >= 400:
                _raise_for_error(resp)
            return resp.json()
        raise SandboxError(f"Network error: {last}")

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def _create(self, template, size, timeout, env, metadata):
        data = self._request("POST", "/sandboxes/", json={
            "template": template, "size": size, "timeout_seconds": timeout,
            "env": env, "metadata": metadata,
        })
        self.id = data["id"]
        self.public_host = data.get("public_host")
        self.state = data.get("state", "running")

    @classmethod
    def connect(cls, sandbox_id: str, api_key: str | None = None,
                base_url: str = DEFAULT_BASE_URL) -> "Sandbox":
        """Подключиться к уже созданной песочнице по её id (sbx_…)."""
        sbx = cls(api_key=api_key, base_url=base_url, _lazy=True)
        data = sbx._request("GET", f"/sandboxes/{sandbox_id}/", retryable=True)
        sbx.id = data["id"]
        sbx.public_host = data.get("public_host")
        sbx.state = data.get("state", "unknown")
        return sbx

    def kill(self) -> None:
        """Остановить песочницу (идемпотентно). Останавливает биллинг."""
        if not self.id or self.state in ("stopped", "expired", "failed"):
            return
        self._request("DELETE", f"/sandboxes/{self.id}/", retryable=True)
        self.state = "stopped"

    def set_timeout(self, timeout_seconds: int) -> None:
        """Новый TTL от текущего момента (продление резервирует минуты)."""
        self._request("POST", f"/sandboxes/{self.id}/timeout/",
                      json={"timeout_seconds": timeout_seconds})

    def refresh(self) -> str:
        data = self._request("GET", f"/sandboxes/{self.id}/", retryable=True)
        self.state = data.get("state", self.state)
        return self.state

    # ── exec ──────────────────────────────────────────────────────────────────

    def exec(self, command: str = "", code: str = "", language: str = "python",
             timeout: int = 60, cwd: str = "/home/user",
             background: bool = False) -> ExecResult:
        """Выполнить shell-команду ИЛИ код (code + language)."""
        payload = {"language": language, "timeout_seconds": timeout,
                   "cwd": cwd, "background": background}
        if command:
            payload["command"] = command
        if code:
            payload["code"] = code
        data = self._request("POST", f"/sandboxes/{self.id}/exec/",
                             json=payload, timeout=timeout + 60)
        return ExecResult(**{k: data[k] for k in
                             ("exit_code", "stdout", "stderr", "duration_ms", "truncated")})

    # ── files ─────────────────────────────────────────────────────────────────

    def write_file(self, path: str, content) -> None:
        """Записать файл. content — str (utf-8) или bytes (base64 под капотом)."""
        if isinstance(content, bytes):
            item = {"path": path, "content": base64.b64encode(content).decode(),
                    "encoding": "base64"}
        else:
            item = {"path": path, "content": content, "encoding": "utf-8"}
        self._request("POST", f"/sandboxes/{self.id}/files/", json={"files": [item]})

    def write_files(self, files: dict) -> None:
        """Записать несколько файлов: {path: content(str|bytes)}."""
        items = []
        for path, content in files.items():
            if isinstance(content, bytes):
                items.append({"path": path, "content": base64.b64encode(content).decode(),
                              "encoding": "base64"})
            else:
                items.append({"path": path, "content": content, "encoding": "utf-8"})
        self._request("POST", f"/sandboxes/{self.id}/files/", json={"files": items})

    def read_file(self, path: str):
        """Прочитать файл. Возвращает str, для бинарных — bytes."""
        data = self._request("GET", f"/sandboxes/{self.id}/files/",
                             params={"path": path}, retryable=True)
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"])
        return data["content"]

    def list_dir(self, path: str = "/home/user") -> list:
        data = self._request("GET", f"/sandboxes/{self.id}/files/",
                             params={"path": path, "op": "list"}, retryable=True)
        return data.get("entries", [])

    def logs(self, lines: int = 100) -> list:
        data = self._request("GET", f"/sandboxes/{self.id}/logs/",
                             params={"lines": lines}, retryable=True)
        return data.get("lines", [])

    def url(self, port: int = 3000) -> str:
        """Публичный URL веб-сервера, запущенного внутри (exec background)."""
        if not self.public_host:
            raise SandboxError("Sandbox has no public host")
        host = self.public_host
        if "-" in host.split(".")[0]:
            # хост уже включает порт (формат <port>-<id>.домен)
            base = host.split("-", 1)[1]
            return f"https://{port}-{base}"
        return f"https://{host}"

    # ── context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.kill()
        except AineronError:
            pass

    def __repr__(self) -> str:
        return f"<Sandbox {self.id} state={self.state}>"
