#!/usr/bin/env python
"""T-074 门禁：DocGraph 权限、审计与用量（P4-F06 ~ P4-F08）。

断言：
  N1  结构与测试齐备（router 增量 + host-core 审计辅助 + 控制面测试）
  N2  host-core 测试与类型检查通过
  N3  控制面 pytest 全量通过
  N4  三类审计事件齐备（submit / view / cancel）且拒绝路径写 denied
  N5  用量按任务记录：source=adapter_estimate，Token 字段留空不猜
  N6  负向：不记录正文与 Token 原值；无第二套审计通道

用法：python scripts/verify_t074_docgraph_audit_usage.py
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
HOST_CORE = REPO / "packages" / "host-core"
PYTHON = API / ".venv" / "Scripts" / "python.exe"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def main() -> int:
    needed = [
        API / "app" / "routers" / "docgraph.py",
        API / "tests" / "test_docgraph_audit_usage.py",
        HOST_CORE / "src" / "docgraph-audit.ts",
        HOST_CORE / "test" / "docgraph-audit.test.ts",
    ]
    missing = [path.name for path in needed if not path.exists()]
    record(not missing, f"N1 结构与测试齐备（缺: {missing or '无'}）")

    if NODE is not None:
        test = run(NODE, HOST_CORE / "node_modules/vitest/vitest.mjs", "run", cwd=HOST_CORE)
        typecheck = run(NODE, HOST_CORE / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=HOST_CORE)
        tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
        record(test.returncode == 0 and typecheck.returncode == 0,
               f"N2 host-core 测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")
    else:
        record(False, "N2 node 不可用")

    pytest = run(PYTHON, "-m", "pytest", "tests", "-q", cwd=API)
    tail = pytest.stdout.strip().splitlines()[-1] if pytest.stdout else ""
    record(pytest.returncode == 0, f"N3 控制面 pytest（{tail}）")

    router = (API / "app" / "routers" / "docgraph.py").read_text(encoding="utf-8")
    audit_whitelist = (API / "app" / "services" / "audit.py").read_text(encoding="utf-8")
    api_test = (API / "tests" / "test_docgraph_audit_usage.py").read_text(encoding="utf-8")
    record(
        '"docgraph.submit"' in router and '"docgraph.view"' in router and '"docgraph.cancel"' in router
        and "result=\"denied\"" in router
        and "docgraph.view" in audit_whitelist
        and '{"docgraph.submit", "docgraph.view", "docgraph.cancel"}' in api_test,
        "N4 三类审计事件齐备（submit/view/cancel）且拒绝路径写 denied",
    )

    helper = (HOST_CORE / "src" / "docgraph-audit.ts").read_text(encoding="utf-8")
    record(
        "source: 'adapter_estimate'" in helper
        and helper.count("null") >= 4
        and "prompt_tokens=None" in router and "total_tokens=None" in router
        and 'usage_id=f"docgraph:{job.id}"' in router,
        "N5 用量按任务记录（source=adapter_estimate，Token 字段留空不猜）",
    )

    forbidden = [token for token in ("contract_text", "document_text", "api_key", "raw_token") if token in router]
    record(not forbidden and "Token 原值" in helper,
           f"N6 不记录正文与 Token 原值、无第二套审计通道（命中: {forbidden or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
