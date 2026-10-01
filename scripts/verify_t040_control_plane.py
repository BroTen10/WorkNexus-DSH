#!/usr/bin/env python
"""T-040 门禁：控制面骨架、健康检查与 PG17 迁移基线。

断言：
  K1  结构齐备
  K2  pytest 健康检查通过
  K3  PG17 容器健康
  K4  Alembic 在 PG17 上 upgrade head / downgrade base
  K5  不引入官方会话链路依赖

用法：python scripts/verify_t040_control_plane.py
"""

from __future__ import annotations

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


def run(*args: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(arg) for arg in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = ["pyproject.toml", "docker-compose.yml", ".env.example", "alembic.ini", "app/main.py",
            "app/config.py", "app/db.py", "app/security/jwt.py", "migrations/env.py", "tests/test_health.py"]
    missing = [item for item in need if not (API / item).exists()]
    record(not missing, f"K1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    record(test.returncode == 0, f"K2 pytest 退出码 {test.returncode}（{test.stdout.strip().splitlines()[-1] if test.stdout else ''}）")

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    record(state == "healthy", f"K3 PG17 容器健康状态 {state or 'missing'}")

    if state == "healthy":
        env = dict(__import__("os").environ, DATABASE_URL=PG_URL)
        up = subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=str(API),
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=300, env=env)
        down = subprocess.run([str(PYTHON), "-m", "alembic", "downgrade", "base"], cwd=str(API),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=300, env=env)
        record(up.returncode == 0 and down.returncode == 0,
               f"K4 PG17 迁移可升可降（upgrade={up.returncode}, downgrade={down.returncode}）")
    else:
        record(False, "K4 PG17 容器不可用，迁移未执行")

    source = "\n".join((API / "app" / item).read_text(encoding="utf-8") for item in ("main.py", "config.py", "db.py"))
    tokens = [token for token in ("@deepseek-ai/dsh", "DSH_SESSION_TOKEN", "api-gateway") if token in source]
    record(not tokens, f"K5 不引入官方会话链路依赖（命中: {tokens or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
