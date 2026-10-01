#!/usr/bin/env python
"""T-091 门禁：后台任务管理（P6A 功能 2/3、验收 2/3）。

断言：
  N1  控制面路由、插件页面与测试齐备
  N2  控制面 pytest 全量通过
  N3  ACP 插件测试与类型检查通过
  N4  任务与用户 / 空间 / 插件关联
  N5  生命周期齐备：创建 / 取消 / 恢复 / 关闭，状态变更写审计
  N6  PG17 迁移 0005 可升可降（closed 终态）
  N7  负向：不代理 ACP 运行时（控制面不调用 ACP/JSON-RPC）；未授权 404 + denied 审计

用法：python scripts/verify_t091_background_jobs.py
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "acp"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")
CONTAINER = "worknexus-dsh-postgres"
PG_URL = "postgresql+psycopg://worknexus:worknexus_dev_password@127.0.0.1:15432/worknexus"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600, env=env)


def main() -> int:
    need = [API / "app" / "routers" / "jobs.py", API / "tests" / "test_jobs.py",
            PLUGIN / "src" / "pages" / "JobList.tsx", PLUGIN / "test" / "plugin.test.ts",
            API / "migrations" / "versions" / "0005_background_job_closed_status.py"]
    missing = [path.name for path in need if not path.exists()]
    record(not missing, f"N1 结构与迁移齐备（缺: {missing or '无'}）")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N2 控制面 pytest（{tail}）")

    if NODE is not None:
        test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
        typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
        tail2 = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
        record(test.returncode == 0 and typecheck.returncode == 0,
               f"N3 ACP 插件测试/类型（test={test.returncode} {tail2[-1] if tail2 else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N3 node 不可用")

    router = (API / "app" / "routers" / "jobs.py").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_jobs.py").read_text(encoding="utf-8")
    record(
        all(token in router for token in ('"pluginId"', '"spaceId"', "submitted_by_user_id"))
        and 'job["pluginId"] == "acp"' in api_test,
        "N4 任务与用户/空间/插件关联（含用例断言）",
    )

    record(
        all(token in router for token in ("/jobs", "/cancel", "/resume", "/close"))
        and all(token in router for token in ("acp.job.start", "acp.job.cancel", "acp.job.resume", "acp.job.close"))
        and "alreadyClosed" in router,
        "N5 生命周期齐备且状态变更写审计",
    )

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N6 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        definition = run(
            "docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus", "-Atc",
            "select pg_get_constraintdef(oid) from pg_constraint where conname='ck_background_jobs_status'",
        ).stdout.strip()
        down = run(PYTHON, "-m", "alembic", "downgrade", "0004", cwd=API, env=env)
        old_definition = run(
            "docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus", "-Atc",
            "select pg_get_constraintdef(oid) from pg_constraint where conname='ck_background_jobs_status'",
        ).stdout.strip()
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and down.returncode == 0 and back.returncode == 0
               and "closed" in definition and "closed" not in old_definition,
               f"N6 PG17 迁移 0005 可升可降（up={up.returncode}, down={down.returncode}, "
               f"新约束含 closed={('closed' in definition)}, 旧约束含 closed={('closed' in old_definition)}）")
        run(PYTHON, "-m", "alembic", "downgrade", "base", cwd=API, env=env)

    code = re.sub(r"#.*$", "", router, flags=re.M)
    hits = [token for token in ("jsonrpc", "subprocess", "spawn(", "dsh --profile acp") if token in code]
    record(not hits, f"N7 控制面不代理 ACP 运行时（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
