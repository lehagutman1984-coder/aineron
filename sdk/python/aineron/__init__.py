"""
Aineron Sandboxes SDK.

    from aineron import Sandbox

    with Sandbox(template="python") as sbx:
        result = sbx.exec(code="print(2+2)")
        print(result.stdout)  # "4"

Ключ API: аргумент api_key или переменная окружения AINERON_API_KEY
(ключ создаётся на https://aineron.ru/account/keys/ со скоупом «sandboxes»).
"""
from .sandbox import (
    AineronError,
    AuthenticationError,
    ExecResult,
    InsufficientBalanceError,
    RateLimitError,
    Sandbox,
    SandboxError,
)

__version__ = "0.1.0"
__all__ = [
    "Sandbox",
    "ExecResult",
    "AineronError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "RateLimitError",
    "SandboxError",
]
