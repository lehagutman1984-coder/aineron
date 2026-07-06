"""
Smoke-тест Sandbox API (SB-1): create → files → exec → logs → delete.

Запуск (нужен работающий preview-service и валидный E2B_API_KEY):
    PREVIEW_URL=http://localhost:8001 PREVIEW_INTERNAL_TOKEN=... python spikes/sandbox_smoke.py

Критерии приёмки:
  - полный цикл < 15 c;
  - exec с timeout=2 на sleep 10 → exit_code 124, VM жива;
  - DELETE дважды → оба раза ok.
"""
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = os.environ.get("PREVIEW_URL", "http://localhost:8001")
TOKEN = os.environ.get("PREVIEW_INTERNAL_TOKEN", "changeme-in-production")


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Internal-Token": TOKEN, "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main():
    sid = str(uuid.uuid4())
    t0 = time.perf_counter()

    print("1. create ...")
    created = call("POST", "/sandbox/create", {
        "session_id": sid, "template": "base", "size": "standard",
        "ttl": 180, "env": {"SMOKE": "1"}, "user_id": "smoke",
    })
    print("   ", created)
    assert created["session_id"] == sid

    print("2. write files ...")
    w = call("POST", f"/sandbox/{sid}/files", {
        "files": [{"path": "/home/user/main.py", "content": "print(2+2)"}],
    })
    assert w["written"] == 1, w

    print("3. exec ...")
    r = call("POST", f"/sandbox/{sid}/exec", {"command": "python3 /home/user/main.py"})
    print("   ", r)
    assert r["exit_code"] == 0 and r["stdout"].strip() == "4", r

    print("4. exec code+language ...")
    r = call("POST", f"/sandbox/{sid}/exec", {"code": "import os; print(os.environ.get('SMOKE'))"})
    assert r["exit_code"] == 0 and r["stdout"].strip() == "1", r

    print("5. exec timeout (sleep 10, timeout 2) ...")
    r = call("POST", f"/sandbox/{sid}/exec", {"command": "sleep 10", "timeout": 2})
    assert r["exit_code"] != 0, r
    r2 = call("POST", f"/sandbox/{sid}/exec", {"command": "echo alive"})
    assert r2["stdout"].strip() == "alive", "VM must survive exec timeout"

    print("6. background exec + logs ...")
    call("POST", f"/sandbox/{sid}/exec", {"command": "echo bg-marker", "background": True})
    time.sleep(2)
    logs = call("GET", f"/sandbox/{sid}/logs?lines=50")
    assert any("bg-marker" in ln for ln in logs["lines"]), logs

    print("7. read file back ...")
    f = call("GET", f"/sandbox/{sid}/files?path=/home/user/main.py")
    assert f["content"] == "print(2+2)", f

    print("8. delete (twice, idempotent) ...")
    d1 = call("DELETE", f"/sandbox/{sid}")
    d2 = call("DELETE", f"/sandbox/{sid}")
    assert d1["ok"] and d2["ok"] and d2["already_gone"], (d1, d2)
    print("   duration_seconds:", round(d1["duration_seconds"], 1))

    print(f"\nOK — full cycle in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("SMOKE FAILED:", e)
        sys.exit(1)
