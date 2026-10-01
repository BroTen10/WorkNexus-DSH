#!/usr/bin/env python
"""T-046 门禁：审计只追加、查询、导出与治理。

断言：
  A1  结构齐备
  A2  pytest 全量通过
  A3  Host Core AuditSink 测试与类型检查通过
  A4  九类事件族白名单覆盖
  A5  负向：无审计 PATCH/PUT/DELETE；导出与 purge 路由存在

用法：python scripts/verify_t046_audit.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
API = REPO / "services" / "api"
HOST = REPO / "packages" / "host-core"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = [API / "app/services/audit.py", API / "app/routers/audit.py",
            API / "tests/test_audit.py", HOST / "src/audit-sink.ts", HOST / "test/audit-sink.test.ts"]
    missing = [str(item) for item in need if not item.exists()]
    record(not missing, f"A1 结构齐备（缺: {missing or '无'}）")

    test = run(PYTHON, "-m", "pytest", "tests/test_audit.py", "-q", cwd=API)
    tail = test.stdout.strip().splitlines()[-1] if test.stdout else ""
    record(test.returncode == 0, f"A2 Python 审计测试退出码 {test.returncode}（{tail}）")

    if NODE is None:
        record(False, "A3 node 不可用")
        return finish()
    js_test = run(NODE, HOST / "node_modules/vitest/vitest.mjs", "run", "audit-sink", cwd=HOST)
    js_type = run(NODE, HOST / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=HOST)
    record(js_test.returncode == 0 and js_type.returncode == 0,
           f"A3 Host Core AuditSink（test={js_test.returncode}, typecheck={js_type.returncode}）")

    required = {
        "auth.login", "organization.create", "member.role_assign", "plugin.install", "plugin.update",
        "plugin.enable", "plugin.disable", "plugin.uninstall", "kb.bind", "docgraph.submit",
        "docgraph.cancel", "budget.update", "client.version.upgrade",
    }
    probe = run(PYTHON, "-c", "from app.services.audit import AUDIT_ACTIONS; print(','.join(sorted(AUDIT_ACTIONS)))", cwd=API)
    present = set(probe.stdout.strip().split(","))
    record(required <= present, f"A4 九类事件族覆盖（缺: {sorted(required - present) or '无'}）")

    router = (API / "app/routers/audit.py").read_text(encoding="utf-8")
    bad = [token for token in ("@router.patch", "@router.put", "@router.delete") if token in router]
    good = all(token in router for token in ("/export", "/corrections", "/purge", "/events"))
    record(not bad and good, f"A5 只追加且治理接口齐备（命中: {bad or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
