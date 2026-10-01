#!/usr/bin/env python
"""T-090 门禁：复用官方 ACP 的企业适配（P6A 功能 1）。

断言：
  N1  适配层与测试齐备
  N2  kernel-dsh 测试与类型检查通过
  N3  官方事实（启动命令 / 官方客户端 / 能力面）写入实现并可被断言
  N4  不支持能力显式返回 unsupported（删除 / fork / 转录回放 / 附加目录）
  N5  企业侧职责齐备（任务关联、权限前置、审计与用量、异常映射）
  N6  负向：不自研 JSON-RPC / 不复刻 ACP 协议；无第二套 Transport 实现

用法：python scripts/verify_t090_acp_transport.py
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
PKG = REPO / "packages" / "kernel-dsh"
NODE = shutil.which("node")

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def main() -> int:
    need = ["src/acp-transport.ts", "test/acp-transport.test.ts", "test/transport.contract.ts",
            "test/fake-acp-client.ts"]
    missing = [item for item in need if not (PKG / item).exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test = run(NODE, PKG / "node_modules/vitest/vitest.mjs", "run", cwd=PKG)
    typecheck = run(NODE, PKG / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PKG)
    tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 kernel-dsh 测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    src = (PKG / "src" / "acp-transport.ts").read_text(encoding="utf-8")
    record(
        "pnpm dsh --profile acp" in src and "@deepseek-ai/dsh-subagent-acp" in src
        and all(token in src for token in ("session/new", "session/resume", "session/close",
                                           "session/set_config_option", "session/prompt", "session/cancel")),
        "N3 官方启动方式/客户端/能力面已取证并写入实现",
    )

    tests = (PKG / "test" / "acp-transport.test.ts").read_text(encoding="utf-8")
    record(
        all(token in src for token in ("session.delete", "session.fork", "transcript.replay",
                                       "session.additionalDirectory"))
        and "requestUnsupportedCapability" in tests,
        "N4 不支持能力显式返回 unsupported（含用例）",
    )

    record(
        all(token in src for token in ("AcpEnterpriseContext", "canRunTool", "audit", "usage", "acp-runtime-error")),
        "N5 企业侧职责齐备（关联/权限前置/审计/用量/异常映射）",
    )

    code = strip_comments(src)
    protocol_hits = [token for token in ("jsonrpc", "createInterface", "spawn(", "readline") if token in code]
    implementations = []
    for candidate in sorted((REPO / "packages").glob("*/src/*.ts")):
        if candidate.parent.parent.name == "kernel-dsh":
            continue
        if re.search(r"create[A-Za-z]*Transport\s*\(", strip_comments(candidate.read_text(encoding="utf-8"))):
            implementations.append(str(candidate.relative_to(REPO)))
    record(not protocol_hits and not implementations,
           f"N6 不自研 JSON-RPC/协议实现，且无第二套 Transport（协议命中: {protocol_hits or '无'}；实现: {implementations or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
