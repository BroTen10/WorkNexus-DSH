#!/usr/bin/env python
"""T-031 门禁：企业插件声明规范与兼容性校验。

断言：
  M1  包结构齐备（manifest 模块 + 单测）
  M2  类型构建通过（tsc）
  M3  单测通过（vitest）
  M4  运行时：§5.2 字段可解析；官方 bundle 字段与企业字段共存；protected 可判定
  M5  运行时：未知权限、非法治理字段与不满足 DSH/Host Core 的声明被拒
  M6  负向：声明模块不实现第二套插件装载器 / 生命周期

用法：python scripts/verify_t031_manifest.py
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
PKG = REPO / "packages" / "plugin-runtime"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = ["package.json", "tsconfig.json", "src/manifest.ts", "src/index.ts", "test/manifest.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"M1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"M2 类型构建退出码 {tsc.returncode}"
           + ("" if tsc.returncode == 0 else f"（{tsc.stdout.strip()[:160]}）"))

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [line.strip() for line in (vit.stdout or "").splitlines() if "Tests" in line]
    record(vit.returncode == 0, f"M3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    declaration = {
        "id": "worknexus.knowledge",
        "name": "Knowledge",
        "version": "1.0.0",
        "type": "service",
        "dshCompatibility": ">=0.2.0-rc.1 <0.3.0",
        "hostCoreCompatibility": ">=1.0.0",
        "protected": True,
        "permissions": ["kb.retrieve", "space.read"],
        "uiSlots": [],
        "governance": {"source": "private-registry", "approval": "none"},
        "peerDependencies": {"@deepseek-ai/cordis": "workspace:~"},
        "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
    }
    probe = (
        "import('./dist/index.js').then(m=>{"
        "const d=" + json.dumps(declaration, ensure_ascii=False) + ";"
        "const ok=m.parseEnterpriseDeclaration(d);"
        "const bad=m.parseEnterpriseDeclaration({...d,permissions:['root.everything']});"
        "const badGov=m.parseEnterpriseDeclaration({...d,governance:{source:'manual',approval:'automatic'}});"
        "const comp=m.checkCompatibility(ok.ok?ok.declaration:d,{dshVersion:'0.2.0-rc.1',hostCoreVersion:'1.0.0'});"
        "const badDsh=m.checkCompatibility(ok.ok?ok.declaration:d,{dshVersion:'0.3.0',hostCoreVersion:'1.0.0'});"
        "const badCore=m.checkCompatibility(ok.ok?ok.declaration:d,{dshVersion:'0.2.0-rc.1',hostCoreVersion:'0.9.0'});"
        "console.log(JSON.stringify({ok,bad,badGov,comp,badDsh,badCore}));})"
    )
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    parsed = info.get("ok") or {}
    record(
        parsed.get("ok") is True
        and parsed.get("declaration", {}).get("protected") is True
        and parsed.get("declaration", {}).get("permissions") == ["kb.retrieve", "space.read"]
        and parsed.get("declaration", {}).get("dsh", {}).get("bundle", {}).get("patch") == "./cordis.patch.yml"
        and parsed.get("declaration", {}).get("peerDependencies", {}).get("@deepseek-ai/cordis") == "workspace:~",
        "M4 声明可解析；官方字段与企业字段共存；protected 可判定",
    )

    bad = info.get("bad") or {}
    bad_gov = info.get("badGov") or {}
    compat = info.get("comp") or {}
    bad_dsh = info.get("badDsh") or {}
    bad_core = info.get("badCore") or {}
    record(
        bad.get("ok") is False and any("permissions" in item for item in bad.get("problems", []))
        and bad_gov.get("ok") is False and any("governance" in item for item in bad_gov.get("problems", [])),
        "M5a 未知权限与非法治理字段被拒",
    )
    record(
        compat.get("ok") is True and compat.get("problems") == []
        and bad_dsh.get("ok") is False and any("dshCompatibility" in item for item in bad_dsh.get("problems", []))
        and bad_core.get("ok") is False and any("hostCoreCompatibility" in item for item in bad_core.get("problems", [])),
        "M5b 兼容性：匹配通过；DSH / Host Core 不匹配拒绝",
    )

    src = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in ("manifest.ts", "index.ts"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [t for t in ("enablePlugin", "disablePlugin", "installBundle", "removeBundle", "loadPlugin", "unloadPlugin") if t in code]
    record(not hits, f"M6 不实现第二套插件装载器 / 生命周期（命中: {hits or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad_count = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad_count} [FAIL]")
    return 1 if bad_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
