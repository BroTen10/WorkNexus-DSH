#!/usr/bin/env python
"""T-102 门禁：插件白名单与安装审批（P6B-F02/F03、§3.5）。

断言：
  N1  控制面路由、插件审批提示与测试齐备
  N2  控制面 pytest 全量通过
  N3  插件测试与类型检查通过
  N4  企业模式未过白名单不可安装（403 not_whitelisted + denied 审计）
  N5  审批可追踪（请求人/决定人/时间/理由）且批准后进入白名单
  N6  个人模式不强制白名单，只记录（§3.5）
  N7  PG17 迁移 0007 可升可降（治理两张表）

用法：python scripts/verify_t102_market_approval.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
PLUGIN = REPO / "plugins" / "market"
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


def psql(sql: str) -> str:
    return run("docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus", "-Atc", sql).stdout.strip()


def main() -> int:
    need = [API / "app" / "routers" / "market_approval.py", API / "tests" / "test_market_approval.py",
            PLUGIN / "src" / "approval.tsx", PLUGIN / "test" / "approval.test.tsx",
            API / "migrations" / "versions" / "0007_plugin_market_governance.py"]
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
               f"N3 插件测试/类型（test={test.returncode} {tail2[-1] if tail2 else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N3 node 不可用")

    router = (API / "app" / "routers" / "market_approval.py").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_market_approval.py").read_text(encoding="utf-8")
    record(
        "not_whitelisted" in router and 'result="denied"' in router
        and 'row["action"] == "plugin.install" and row["result"] == "denied"' in api_test,
        "N4 企业模式未过白名单不可安装（403 + denied 审计）",
    )

    record(
        all(token in router for token in ("requested_by_user_id", "decided_by_user_id", "decided_at", "reason"))
        and "approval_flow_is_traceable" in api_test
        and '"market.approval.request", "market.approval.decide"' in api_test,
        "N5 审批可追踪（请求人/决定人/时间/理由）且批准后入白名单",
    )

    approval_tsx = (PLUGIN / "src" / "approval.tsx").read_text(encoding="utf-8")
    record(
        "personal" in router and "market.install_requested" in router
        and "recorded-only" in approval_tsx
        and "personal_mode_does_not_enforce_whitelist" in api_test,
        "N6 个人模式不强制白名单，只记录（含用例）",
    )

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N7 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        created = psql("select count(*) from information_schema.tables "
                       "where table_name in ('plugin_whitelist_entries','plugin_approval_requests')")
        down = run(PYTHON, "-m", "alembic", "downgrade", "0006", cwd=API, env=env)
        dropped = psql("select count(*) from information_schema.tables "
                       "where table_name in ('plugin_whitelist_entries','plugin_approval_requests')")
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and down.returncode == 0 and back.returncode == 0
               and created == "2" and dropped == "0",
               f"N7 PG17 迁移 0007 可升可降（up={up.returncode}, down={down.returncode}, "
               f"head 两表={created}, 降级后={dropped}）")
        run(PYTHON, "-m", "alembic", "downgrade", "base", cwd=API, env=env)

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
