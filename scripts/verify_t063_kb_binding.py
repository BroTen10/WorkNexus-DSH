#!/usr/bin/env python
"""T-063 门禁：知识库空间绑定与会话继承（P3-F03 / P3-F04）。

断言：
  N1  结构与迁移齐备
  N2  插件测试与类型检查通过
  N3  控制面 pytest 全量通过
  N4  绑定范围只允许部门或项目空间之一（无会话级绑定）
  N5  绑定与配置变更写审计（§6.2 第 5 类）
  N6  PG17 迁移 0003 可升可降，`weight` 列同步出现/消失
  N7  负向：无会话级绑定字段、无第二套凭据存储

用法：python scripts/verify_t063_kb_binding.py
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
PLUGIN = REPO / "plugins" / "knowledge"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")
CONTAINER = "worknexus-dsh-postgres"
PG_URL = "postgresql+psycopg://worknexus:worknexus_dev_password@127.0.0.1:15432/worknexus"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None, env: dict[str, str] | None = None,
        timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)


def psql(sql: str) -> str:
    return run("docker", "exec", CONTAINER, "psql", "-U", "worknexus", "-d", "worknexus", "-Atc", sql).stdout.strip()


def weight_column_present() -> bool:
    return psql(
        "select count(*) from information_schema.columns "
        "where table_name='knowledge_bindings' and column_name='weight'"
    ) == "1"


def main() -> int:
    needed = [
        PLUGIN / "src" / "binding.ts",
        PLUGIN / "test" / "binding.test.ts",
        API / "app" / "routers" / "kb.py",
        API / "tests" / "test_kb_binding.py",
        API / "migrations" / "versions" / "0003_knowledge_binding_weight.py",
    ]
    missing = [path.name for path in needed if not path.exists()]
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
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N3 控制面 pytest（{tail}）")

    router = (API / "app" / "routers" / "kb.py").read_text(encoding="utf-8")
    binding_src = (PLUGIN / "src" / "binding.ts").read_text(encoding="utf-8")
    record(
        "必须且只能指定部门或项目空间之一" in router
        and "session_id" not in router
        and "kind: 'project' | 'department'" in binding_src,
        "N4 绑定范围为部门/项目空间之一，无会话级绑定",
    )

    audit_tokens = [token for token in ('"kb.create"', '"kb.update"', '"kb.bind"', '"kb.unbind"') if token in router]
    api_test = (API / "tests" / "test_kb_binding.py").read_text(encoding="utf-8")
    record(
        len(audit_tokens) == 4 and "kb.bind" in api_test and "kb.unbind" in api_test,
        f"N5 绑定/配置变更写审计（{', '.join(audit_tokens)}）",
    )

    state = run("docker", "inspect", "--format", "{{.State.Health.Status}}", CONTAINER).stdout.strip()
    if state != "healthy":
        record(False, f"N6 PG17 容器状态 {state or 'missing'}")
    else:
        env = dict(os.environ, DATABASE_URL=PG_URL)
        up = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        after_up = weight_column_present()
        mid = run(PYTHON, "-m", "alembic", "downgrade", "0002", cwd=API, env=env)
        after_down = weight_column_present()
        back = run(PYTHON, "-m", "alembic", "upgrade", "head", cwd=API, env=env)
        record(up.returncode == 0 and mid.returncode == 0 and back.returncode == 0
               and after_up and not after_down,
               f"N6 PG17 迁移 0003 可升可降（up={up.returncode}, down={mid.returncode}, "
               f"weight上={after_up}/下={after_down}）")
        run(PYTHON, "-m", "alembic", "downgrade", "base", cwd=API, env=env)

    forbidden = [token for token in ("Keychain", "credential_store", "encrypted_blob") if token in router]
    record(not forbidden, f"N7 无会话级绑定字段 / 无第二套凭据存储（命中: {forbidden or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
