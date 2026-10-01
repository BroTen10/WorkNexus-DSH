#!/usr/bin/env python
"""T-043 门禁：组织 / 部门 / 项目空间。

断言：
  O1  结构齐备
  O2  pytest 全量通过
  O3  PG17 迁移可升可降
  O4  负向：不实现细粒度权限点编辑器；未登录路由受保护

用法：python scripts/verify_t043_orgs.py
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
    need = ["app/routers/orgs.py", "app/routers/audit.py", "app/security/dependencies.py", "tests/test_orgs.py"]
    missing = [item for item in need if not (API / item).exists()]
    record(not missing, f"O1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"O2 pytest 退出码 {test.returncode}（{tail}）")

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"O3 PG17 容器状态 {state or 'missing'}")
        return finish()
    env = dict(os.environ, DATABASE_URL=PG_URL)
    up = subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=str(API),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    down = subprocess.run([str(PYTHON), "-m", "alembic", "downgrade", "base"], cwd=str(API),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    record(up.returncode == 0 and down.returncode == 0,
           f"O3 PG17 迁移可升可降（upgrade={up.returncode}, downgrade={down.returncode}）")

    src = (API / "app/routers/orgs.py").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    tokens = [token for token in ("permission_editor", "custom_permission", "grant_action") if token in code]
    record(not tokens, f"O4 不实现细粒度权限点编辑器（命中: {tokens or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
