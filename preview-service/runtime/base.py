from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class Stack(str, Enum):
    NEXTJS = "nextjs"
    PYTHON = "python"
    DJANGO = "django"
    TELEGRAM_BOT = "telegram_bot"


class SessionState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class PreviewSession:
    session_id: str
    project_id: str
    public_url: str           # Cloudflare Tunnel URL
    internal_sandbox_id: str  # e2b sandbox id — не отдавать наружу
    expires_at: float         # epoch seconds


@dataclass
class SessionStatus:
    session_id: str
    state: SessionState
    public_url: str | None
    logs_tail: list[str]


class Runtime(ABC):
    @abstractmethod
    def start(
        self,
        project_id: str,
        code_files: dict[str, str],
        stack: Stack,
        ttl: int,
        env: dict[str, str] | None = None,
    ) -> PreviewSession: ...

    @abstractmethod
    def stop(self, session_id: str) -> None: ...

    @abstractmethod
    def status(self, session_id: str) -> SessionStatus: ...


# Sprint 2: реализовать через e2b SDK
class E2BRuntime(Runtime):
    def start(self, project_id, code_files, stack, ttl, env=None) -> PreviewSession:
        raise NotImplementedError("E2BRuntime — Sprint 2")

    def stop(self, session_id):
        raise NotImplementedError

    def status(self, session_id) -> SessionStatus:
        raise NotImplementedError


# Будущее — Вариант B: тот же интерфейс, собственный Firecracker
class FirecrackerRuntime(Runtime):
    def start(self, project_id, code_files, stack, ttl, env=None) -> PreviewSession:
        raise NotImplementedError("FirecrackerRuntime — будущее")

    def stop(self, session_id):
        raise NotImplementedError

    def status(self, session_id) -> SessionStatus:
        raise NotImplementedError
