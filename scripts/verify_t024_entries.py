#!/usr/bin/env python
"""T-024 门禁：企业入口挂载（按运行模式门控）。

断言：
  E1  包结构齐备（package.json / tsconfig.json / src/index.ts / test/entries.test.ts）
  E2  类型构建通过（tsc）
  E3  单测通过（vitest，直接调 node 绕过 pnpm builds 门禁）
  E4  运行时行为：无模式上下文 → personal；个人模式同步后**零入口且不抛错**
  E5  负向：P1 未随发行版预置任何企业入口（四个入口 preinstalled 全为 false）
  E6  负向：实现里没有插件启停能力，也没有官方未提供的插件管理 IPC 通道

用法：python scripts/verify_t024_entries.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "packages" / "ent-entries"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = ["package.json", "tsconfig.json", "src/index.ts", "test/entries.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"E1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"E2 类型构建退出码 {tsc.returncode}")

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [l.strip() for l in (vit.stdout or "").splitlines() if "Tests" in l or "Test Files" in l]
    record(vit.returncode == 0, f"E3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    probe = (
        "import('./dist/index.js').then(m=>{"
        "const host=m.createMemoryEntryHost();"
        "const mode=m.resolveRunMode();"           # 无上下文
        "const sync=m.syncEnterpriseEntries(host,mode);"
        "console.log(JSON.stringify({mode,added:sync.added,removed:sync.removed,list:host.list(),"
        "preinstalled:m.ENTERPRISE_ENTRIES.map(e=>e.preinstalled),enterpriseVisible:m.visibleEntriesFor('enterprise').length}));"
        "}).catch(e=>{console.log(JSON.stringify({error:String(e)}))})"
    )
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}
    record(info.get("mode") == "personal" and info.get("list") == [] and info.get("added") == []
           and info.get("removed") == [],
           f"E4 无上下文 → personal；个人模式零入口不抛错（{info}）")

    record(info.get("preinstalled") == [False, False, False, False] and info.get("enterpriseVisible") == 4,
           f"E5 P1 未预置任何企业入口，企业模式可见数 = {info.get('enterpriseVisible')}")

    src = (PKG / "src" / "index.ts").read_text(encoding="utf-8")
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    exported = re.findall(r"export (?:async )?function (\w+)", code) + re.findall(r"export const (\w+)", code)
    banned = [n for n in exported if any(k in n.lower() for k in ("enableplugin", "disableplugin", "installplugin"))]
    ipc = [t for t in ("ipcRenderer", "ipcMain", "plugin-manager", "electron") if t in code]
    record(not banned and not ipc,
           f"E6 无插件启停能力、无官方未提供的插件管理 IPC（导出: {sorted(set(exported))}；命中: {banned + ipc or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
