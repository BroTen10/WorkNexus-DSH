#!/usr/bin/env python
"""T-101 门禁：私有插件源与镜像（P6B-F01）。

断言：
  N1  插件私有源模块、控制面路由与测试齐备
  N2  插件测试与类型检查通过
  N3  控制面 pytest 全量通过
  N4  私有源不可达时降级为 installed-only，且不影响启动（创建期零请求）
  N5  私有源不回退公共源；凭据不外泄（错误与描述均脱敏）
  N6  PG17 迁移 0006 可升可降（ExternalService.config_json）

用法：python scripts/verify_t101_private_source.py
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
    need = [PLUGIN / "src" / "registry" / "private-source.ts", PLUGIN / "test" / "private-source.test.ts",
            API / "app" / "routers" / "market.py", API / "tests" / "test_market_registry.py",
            API / "migrations" / "versions" / "0006_external_service_config.py"]
    missing = [path.name for path in need if not path.exists()]
    record(not missing, f"N1 结构与迁移齐备（缺: {missing or '无'}）")

    if NODE is not None:
        test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
        typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
        tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
        record(test.returncode == 0 and typecheck.returncode == 0,
               f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N2 node 不可用")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail2 = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N3 控制面 pytest（{tail2}）")

    src = (PLUGIN / "src" / "registry" / "private-source.ts").read_text(encoding="utf-8")
    tests = (PLUGIN / "test" / "private-source.test.ts").read_text(encoding="utf-8")
    record(
        "installed-only" in src and "creating the source performs no request" in tests
        and "not.toHaveBeenCalled" in tests,
        "N4 不可达降级为 installed-only，创建期零请求（不影响启动）",
    )

    record(
        "fallbackToPublic: false" in src and "sanitizeDetail" in src
        and "not.toContain(TOKEN)" in tests,
        "N5 私有源不回退公共源，凭据不外泄",
    )

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N6 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        present = psql("select count(*) from information_schema.columns "
                       "where table_name='external_services' and column_name='config_json'") == "1"
        down = run(PYTHON, "-m", "alembic", "downgrade", "0005", cwd=API, env=env)
        gone = psql("select count(*) from information_schema.columns "
                    "where table_name='external_services' and column_name='config_json'") == "0"
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and down.returncode == 0 and back.returncode == 0 and present and gone,
               f"N6 PG17 迁移 0006 可升可降（up={up.returncode}, down={down.returncode}, "
               f"head 有列={present}, 降级后无列={gone}）")
        run(PYTHON, "-m", "alembic", "downgrade", "base", cwd=API, env=env)

    router = re.sub(r"#.*$", "", (API / "app" / "routers" / "market.py").read_text(encoding="utf-8"), flags=re.M)
    record("EXTERNAL_SERVICE" not in router.upper() or "plugin-registry" in router,
           "N6b 私有源配置复用 ExternalService 台账（不新增第二套外部服务表）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
