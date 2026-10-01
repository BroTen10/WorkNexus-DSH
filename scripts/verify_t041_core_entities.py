#!/usr/bin/env python
"""T-041 门禁：16 个核心实体、约束与 PG17 迁移。

断言：
  E1  16 个实体模型齐备
  E2  pytest 约束用例通过
  E3  PG17 迁移可升可降
  E4  升级后表数量为 19（16 个核心实体 + T-064 检索日志 + T-102 市场治理两张表），降级后为 0
  E5  负向：SessionMeta 无正文列；PluginInstall 声明官方权威

用法：python scripts/verify_t041_core_entities.py
"""

from __future__ import annotations

import os
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
    model_dir = API / "app" / "models"
    needed = ["base.py", "identity.py", "org.py", "audit.py", "usage.py", "plugin.py",
              "session_meta.py", "kb.py", "external.py", "__init__.py"]
    missing = [item for item in needed if not (model_dir / item).exists()]
    record(not missing, f"E1 模型结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"E2 pytest 退出码 {test.returncode}（{tail}）")

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"E3 PG17 容器状态 {state or 'missing'}")
        return finish()

    env = dict(os.environ, DATABASE_URL=PG_URL)
    up = subprocess.run([str(PYTHON), "-m", "alembic", "upgrade", "head"], cwd=str(API),
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    record(up.returncode == 0, f"E3a PG17 upgrade head 退出码 {up.returncode}")

    probe = (
        "import json;"
        "from app.models import SessionMeta;"
        "bad=[n for n in ('prompt','output','transcript','messages','content') if n in SessionMeta.__table__.c];"
        "print(json.dumps({'bad':bad}))"
    )
    inspected = run(PYTHON, "-c", probe, cwd=API).stdout.strip()
    try:
        session_bad = __import__("json").loads(inspected).get("bad", [])
    except Exception:
        session_bad = ["introspection-failed"]
    count = run("docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus",
                "-Atc", "select count(*) from information_schema.tables where table_schema='public' and table_name <> 'alembic_version'").stdout.strip()
    record(count == "19",
           f"E4a 升级后表数量 = {count}（16 核心实体 + 知识库检索日志 + 插件市场治理两张表）")

    down = subprocess.run([str(PYTHON), "-m", "alembic", "downgrade", "base"], cwd=str(API),
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, env=env)
    count = run("docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus",
                "-Atc", "select count(*) from information_schema.tables where table_schema='public' and table_name <> 'alembic_version'").stdout.strip()
    record(down.returncode == 0 and count == "0",
           f"E4b PG17 downgrade base 后核心表数量 = {count or 'blank'}"
           + ("" if down.returncode == 0 else f"（downgrade={down.stderr.strip()[:120]}）"))

    plugin_src = (model_dir / "plugin.py").read_text(encoding="utf-8")
    record(not session_bad and "official-plugin-manager" in plugin_src,
           f"E5 SessionMeta 无正文列；PluginInstall 声明官方权威（命中: {session_bad or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
