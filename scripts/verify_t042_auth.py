#!/usr/bin/env python
"""T-042 门禁：邮箱验证码注册登录。

断言：
  A1  结构齐备
  A2  pytest 全量通过
  A3  PG17 迁移可升可降
  A4  负向：路由源码无 SSO；验证码/密码不写入日志代码

用法：python scripts/verify_t042_auth.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
CONTAINER = "worknexus-dsh-postgres"
PG_URL = "postgresql+psycopg://worknexus:worknexus_dev_password@127.0.0.1:15432/worknexus"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = ["app/routers/auth.py", "app/services/verification.py", "tests/test_auth.py"]
    missing = [item for item in need if not (API / item).exists()]
    record(not missing, f"A1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"A2 pytest 退出码 {test.returncode}（{tail}）")

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"A3 PG17 容器状态 {state or 'missing'}")
        return finish()
    env = dict(os.environ, DATABASE_URL=PG_URL)
    up = subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=str(API),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    down = subprocess.run([str(PYTHON), "-m", "alembic", "downgrade", "base"], cwd=str(API),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    record(up.returncode == 0 and down.returncode == 0,
           f"A3 PG17 迁移可升可降（upgrade={up.returncode}, downgrade={down.returncode}）")

    src = "\n".join((API / item).read_text(encoding="utf-8") for item in
                    ("app/routers/auth.py", "app/services/verification.py"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    tokens = [token for token in ("sso", "SSO", "logger.info(code", "logger.info(password") if token in code]
    record(not tokens, f"A4 无 SSO；验证码/密码不进日志（命中: {tokens or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
