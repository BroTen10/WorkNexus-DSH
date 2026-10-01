#!/usr/bin/env python
"""T-061 门禁：知识库 Provider 连接配置与健康检查。

断言：
  N1  插件结构齐备（官方插件形态）
  N2  插件测试与类型检查通过
  N3  manifest 为官方 bundle 声明，且声明 kb.retrieve / kb.bind / space.read
  N4  四种连接状态可区分（healthy / unreachable / auth_failed / sync_failed）
  N5  凭据边界：不硬编码地址、不读环境变量、凭据不进 detail
  N6  负向：无第二套凭据存储、无插件管理 IPC、无自研向量库/解析流水线

用法：python scripts/verify_t061_knowledge_provider.py
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
PLUGIN = REPO / "plugins" / "knowledge"
NODE = shutil.which("node")
STATES = ["healthy", "unreachable", "auth_failed", "sync_failed"]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def run(*args: Path | str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(item) for item in args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=300)


def source_text() -> str:
    files = sorted((PLUGIN / "src").rglob("*.ts")) + sorted((PLUGIN / "src").rglob("*.tsx"))
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def main() -> int:
    need = ["package.json", "plugin.manifest.json", "cordis.patch.yml", "tsconfig.json",
            "src/index.ts", "src/permissions.ts", "src/providers/http-rag.ts",
            "src/pages/Connections.tsx", "test/http-rag.test.ts", "test/plugin.test.ts"]
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
        manifest.get("dsh", {}).get("bundle", {}).get("patch") == "./cordis.patch.yml"
        and {"space.read", "kb.retrieve", "kb.bind"} <= set(manifest.get("permissions", []))
        and len(manifest.get("uiSlots", [])) >= 1
        and manifest.get("governance", {}).get("source") in {"local", "official", "private-registry"},
        f"N3 manifest 官方 bundle 声明与知识库权限齐备（槽位 {len(manifest.get('uiSlots', []))} 个）",
    )

    provider = (PLUGIN / "src" / "providers" / "http-rag.ts").read_text(encoding="utf-8")
    tests = (PLUGIN / "test" / "http-rag.test.ts").read_text(encoding="utf-8")
    covered = [state for state in STATES if state in provider and state in tests]
    record(len(covered) == 4, f"N4 四态可区分且有测试覆盖（覆盖: {', '.join(covered)}）")

    sanitize_applied = "sanitizeDetail(" in provider and provider.count("sanitizeDetail(") >= 4
    record(sanitize_applied, "N5a 凭据脱敏函数应用于 healthCheck 与凭据解析路径")

    code = re.sub(r"/\*.*?\*/", "", source_text(), flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [token for token in ("process.env", "localStorage", "sessionStorage") if token in code]
    urls = re.findall(r"https?://[^\s'\"`)]+", code)
    record(not hits and not urls,
           f"N5b 不硬编码地址、不读环境变量（命中: {hits or urls or '无'}）")

    forbidden = ["ipcRenderer", "ipcMain", "Keychain", "writeFile", "vectorStore", "embeddingPipeline"]
    second = [token for token in forbidden if token in code]
    record(not second, f"N6 无第二套凭据存储/插件管理 IPC/自研向量库（命中: {second or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
