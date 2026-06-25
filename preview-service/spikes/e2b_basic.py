"""
SPIKE-2: первый E2B sandbox.
Запустить когда E2B_API_KEY будет получен:
    E2B_API_KEY=xxx python preview-service/spikes/e2b_basic.py
"""
import os
import sys

api_key = os.environ.get("E2B_API_KEY")
if not api_key:
    print("Нужен E2B_API_KEY. Зарегистрируйтесь на https://e2b.dev/dashboard")
    sys.exit(1)

from e2b import Sandbox  # pip install e2b

sbx = Sandbox.create(api_key=api_key)
print(f"Sandbox ID: {sbx.sandbox_id}")

result = sbx.commands.run("echo 'hello from E2B'")
print(f"stdout: {result.stdout.strip()}")

result2 = sbx.commands.run("python3 --version")
print(f"Python: {result2.stdout.strip()}")

sbx.kill()
print("Sandbox killed. SPIKE-2 OK.")
