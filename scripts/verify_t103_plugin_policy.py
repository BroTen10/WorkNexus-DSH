#!/usr/bin/env python
"""T-103 门禁：插件版本锁定与兼容性检查（P6B-F04/F05、§5.5）。

断言：
  N1  策略服务、路由增量与测试齐备
  N2  控制面 pytest 全量通过
  N3  缺声明被拒（422 且点名 dshCompatibility / hostCoreCompatibility）
  N4  不兼容范围被拒（422 incompatible，给出具体问题）
  N5  版本锁定阻止自动升级（409 version_locked，且写 market.version.lock 审计）
  N6  semver 含 prerelease 的比较规则正确；契约常量与 packages/contracts 同源
  N7  PG17 迁移 0008 可升可降（锁定列）

用法：python scripts/verify_t103_plugin_policy.py
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
PYTHON = API / ".venv" / "Scripts" / "python.exe"
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
    need = [API / "app" / "services" / "plugin_policy.py",
            API / "tests" / "test_plugin_policy.py",
            API / "migrations" / "versions" / "0008_plugin_version_lock.py"]
    missing = [path.name for path in need if not path.exists()]
    record(not missing, f"N1 结构与迁移齐备（缺: {missing or '无'}）")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N2 控制面 pytest（{tail}）")

    router = (API / "app" / "routers" / "market_approval.py").read_text(encoding="utf-8")
    policy = (API / "app" / "services" / "plugin_policy.py").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_plugin_policy.py").read_text(encoding="utf-8")
    record(
        "invalid_compatibility_declaration" in router
        and "dshCompatibility: 必填" in policy
        and 'assert "dshCompatibility" in str(response.json())' in api_test,
        "N3 缺声明被拒（422 且点名 dshCompatibility / hostCoreCompatibility）",
    )

    record(
        '"incompatible"' in router and "version_in_range" in policy
        and "test_incompatible_range_is_rejected" in api_test,
        "N4 不兼容范围被拒（422 incompatible，给出具体问题）",
    )

    record(
        "upgrade_allowed" in policy and "version_locked" in policy
        and '"version_locked"' in api_test
        and '"market.version.lock"' in router,
        "N5 版本锁定阻止自动升级（409 version_locked + 审计）",
    )

    contracts_version = re.search(
        r"HOST_CORE_CONTRACT_VERSION\s*=\s*'([^']+)'",
        (REPO / "packages" / "contracts" / "src" / "version.ts").read_text(encoding="utf-8"),
    )
    policy_version = re.search(r'CONTRACT_VERSION\s*=\s*"([^"]+)"', policy)
    record(
        "prerelease" in api_test
        and contracts_version is not None and policy_version is not None
        and contracts_version.group(1) == policy_version.group(1),
        f"N6 semver 含 prerelease 规则正确；契约常量同源（{policy_version.group(1) if policy_version else 'n/a'}）",
    )

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N7 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        columns = psql(
            "select count(*) from information_schema.columns "
            "where table_name='plugin_whitelist_entries' and column_name in ('locked','locked_version')"
        )
        down = run(PYTHON, "-m", "alembic", "downgrade", "0007", cwd=API, env=env)
        after = psql(
            "select count(*) from information_schema.columns "
            "where table_name='plugin_whitelist_entries' and column_name in ('locked','locked_version')"
        )
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and down.returncode == 0 and back.returncode == 0
               and columns == "2" and after == "0",
               f"N7 PG17 迁移 0008 可升可降（up={up.returncode}, down={down.returncode}, "
               f"head 两列={columns}, 降级后={after}）")
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
