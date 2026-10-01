#!/usr/bin/env python
"""T-075 门禁：DocGraph Agent 会话联动（P4-F09）。

断言：
  N1  会话联动模块与测试齐备
  N2  插件测试与类型检查通过
  N3  引用带 jobId + spaceId 且可读文本（含原文链接）
  N4  越权结果不得进入会话（空间校验）
  N5  官方未支持能力显式返回不支持并给出降级路径
  N6  负向：不接管交互主链路、不自研 AgentTransport/会话执行

用法：python scripts/verify_t075_docgraph_agent.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "docgraph"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="ignore", timeout=300)


def main() -> int:
    src = PLUGIN / "src" / "agent-bridge.ts"
    test = PLUGIN / "test" / "agent-bridge.test.ts"
    record(src.exists() and test.exists(),
           f"N1 结构齐备（缺: {[p.name for p in (src, test) if not p.exists()] or '无'}）")
    if not src.exists() or NODE is None:
        return finish()

    test_run = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test_run.stdout.splitlines() if "Tests" in l]
    record(test_run.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test_run.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    code = src.read_text(encoding="utf-8")
    tests = test.read_text(encoding="utf-8")
    record(
        "type: 'docgraph.result'" in code and "jobId" in code and "spaceId" in code
        and "找不到" not in code and "docgraph.result" in tests and "3 项风险" in tests,
        "N3 引用含 jobId/spaceId 与可读文本（含原文链接用例）",
    )

    record(
        "referenceIsVisible" in code and "'denied'" in code
        and "keeps out-of-space results out of the session" in tests,
        "N4 越权结果不得进入会话（空间校验 + 用例）",
    )

    record(
        "agent-unsupported" in code and "降级为复制结果摘要到会话" in code
        and "explicit unsupported result" in tests,
        "N5 官方未支持能力显式返回不支持并给出降级路径",
    )

    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    hits = [token for token in ("AgentTransport", "ipcRenderer", "session.execute", "createSession") if token in stripped]
    record(not hits, f"N6 不接管交互主链路、不自研会话执行（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
