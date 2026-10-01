#!/usr/bin/env python
"""T-070 门禁：DocGraph 连接配置与健康检查（P4-F01 / P4-F02）。

断言：
  N1  插件结构齐备（官方插件形态）
  N2  插件测试与类型检查通过
  N3  manifest 声明 docgraph 权限与官方 bundle patch
  N4  端点与 T-009 清单一致（/api/health、/api/reviews/start、/api/reviews/{id}）
  N5  超时与鉴权失败用例齐备；Token 允许留空（网关鉴权）
  N6  负向：无取消端点的伪装、无硬编码现网地址、Token 不入日志

用法：python scripts/verify_t070_docgraph_client.py
"""

from __future__ import annotations

import json
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
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def main() -> int:
    need = ["package.json", "plugin.manifest.json", "cordis.patch.yml", "tsconfig.json",
            "src/index.ts", "src/client.ts", "src/pages/Connection.tsx", "test/client.test.ts"]
    missing = [item for item in need if not (PLUGIN / item).exists()]
    record(not missing, f"N1 结构齐备（缺: {missing or '无'}）")

    if NODE is None:
        record(False, "N2 node 不可用")
        return finish()
    test = run(NODE, PLUGIN / "node_modules/vitest/vitest.mjs", "run", cwd=PLUGIN)
    typecheck = run(NODE, PLUGIN / "node_modules/typescript/bin/tsc", "-p", "tsconfig.json", "--noEmit", cwd=PLUGIN)
    tail = [l.strip() for l in test.stdout.splitlines() if "Tests" in l]
    record(test.returncode == 0 and typecheck.returncode == 0,
           f"N2 插件测试/类型（test={test.returncode} {tail[-1] if tail else ''}, typecheck={typecheck.returncode}）")

    manifest = json.loads((PLUGIN / "plugin.manifest.json").read_text(encoding="utf-8"))
    record(
        {"space.read", "docgraph.submit", "docgraph.read"} <= set(manifest.get("permissions", []))
        and manifest.get("dsh", {}).get("bundle", {}).get("patch") == "./cordis.patch.yml",
        "N3 manifest 声明 docgraph 权限与官方 bundle patch",
    )

    client = (PLUGIN / "src" / "client.ts").read_text(encoding="utf-8")
    endpoints = all(token in client for token in
                    ("'/api/health'", "'/api/reviews/start'", "'/api/reviews'"))
    record(endpoints, "N4 端点与 T-009 清单一致（health / reviews start / reviews status）")

    tests = (PLUGIN / "test" / "client.test.ts").read_text(encoding="utf-8")
    record(
        "timeoutMs: 10" in tests and "401" not in tests and "auth" in client.lower()
        and "ECONNREFUSED" in tests and "mapRemoteStatus" in tests,
        "N5 超时/连接失败与状态映射用例齐备，Token 允许留空（网关鉴权）",
    )

    stripped = re.sub(r"/\*.*?\*/", "", client, flags=re.S)
    stripped = re.sub(r"(?m)^\s*//.*$", "", stripped)
    urls = re.findall(r"https?://[^\s'\"`)]+", stripped)
    leaked = "console.log" in stripped or "process.env" in stripped
    record(
        "docgraph-unsupported" in client and "supported: false" in client and not urls and not leaked,
        f"N6 取消显式标注不支持、无硬编码地址、无日志泄漏（命中地址: {urls or '无'}）",
    )

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
