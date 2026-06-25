"""
SPIKE-3: E2B egress deny-all + allowlist.
Запустить после SPIKE-2:
    E2B_API_KEY=xxx python preview-service/spikes/e2b_egress.py

Ожидаемый результат:
- curl api.telegram.org — успех (в allowlist)
- curl example.com — ошибка/timeout (заблокирован)
"""
import os, sys

api_key = os.environ.get("E2B_API_KEY")
if not api_key:
    print("Нужен E2B_API_KEY.")
    sys.exit(1)

from e2b import Sandbox

# Точную сигнатуру network= подтвердить против актуального SDK при запуске.
# Форма ниже — по docs 2026; если упадёт — проверить e2b.dev/docs/sandbox/internet-access
try:
    sbx = Sandbox.create(
        api_key=api_key,
        network={
            "deny_out": lambda ctx: [ctx.all_traffic],
            "allow_out": ["api.telegram.org", "pypi.org", "files.pythonhosted.org"],
        },
    )
except TypeError:
    # Fallback: старый API без network=
    print("network= не поддерживается в этой версии SDK. Проверьте e2b версию.")
    sys.exit(1)

# Проверяем что allowlist работает
ok = sbx.commands.run("curl -s --max-time 5 https://api.telegram.org/ | head -c 50")
print(f"api.telegram.org: {ok.stdout.strip() or 'timeout/blocked'}")

# Проверяем что deny-all работает
blocked = sbx.commands.run("curl -s --max-time 5 https://example.com/ | head -c 50")
print(f"example.com (should be blocked): {blocked.stdout.strip() or 'BLOCKED OK'}")

sbx.kill()
print("SPIKE-3 done.")
