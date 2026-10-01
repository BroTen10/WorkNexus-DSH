#!/usr/bin/env python
"""T-026 门禁：企业诊断与脱敏上报（客户端侧，需求书 §7.1）。

断言：
  D1  包结构齐备
  D2  类型构建通过（tsc）
  D3  单测通过（vitest）
  D4  运行时：白名单恰为 9 项；白名单外字段被拒并列出
  D5  运行时：个人模式不发送；企业模式 + 开关打开但无控制面也不发送
  D6  负向：实现里不引用官方诊断文件（crash-report / fatal-recovery），不做第二套崩溃采集

用法：python scripts/verify_t026_diagnostics.py
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
PKG = REPO / "packages" / "ent-diagnostics"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = ["package.json", "tsconfig.json", "src/index.ts", "src/redact.ts", "test/diagnostics.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"D1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"D2 类型构建退出码 {tsc.returncode}")

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [l.strip() for l in (vit.stdout or "").splitlines() if "Tests" in l]
    record(vit.returncode == 0, f"D3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    probe = (
        "import('./dist/index.js').then(m=>{"
        "const b=m.buildDiagnosticReport({runtimeVersion:'0.2.0-rc.1',prompt:'x',title:'t',apiKey:'k'});"
        "const personal=m.sendDiagnosticReport(b,{adminEnabled:true,mode:'personal'});"
        "const noCp=m.sendDiagnosticReport(b,{adminEnabled:true,mode:'enterprise'});"
        "const off=m.sendDiagnosticReport(b,{adminEnabled:false,mode:'enterprise'});"
        "const red=m.redactText('Bearer a.b-c sk-abcdefghijklmnop 验证码 654321');"
        "console.log(JSON.stringify({allowed:m.DIAGNOSTIC_ALLOWED_FIELDS.length,"
        "rejected:b.rejectedFields,personal,noCp,off,red,retention:[m.RETENTION_DEFAULT_DAYS,m.RETENTION_MAX_DAYS]}));"
        "}).catch(e=>console.log(JSON.stringify({error:String(e)})))"
    )
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    record(info.get("allowed") == 9 and info.get("rejected") == ["apiKey", "prompt", "title"],
           f"D4 白名单 9 项；越界字段被拒 = {info.get('rejected')}")

    record(info.get("personal") == {"sent": False, "reason": "personal-mode"}
           and info.get("noCp") == {"sent": False, "reason": "control-plane-not-connected"}
           and info.get("off") == {"sent": False, "reason": "disabled"},
           f"D5 三种不发送路径均正确（personal / no-control-plane / disabled）")

    src = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in ("index.ts", "redact.ts"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [t for t in ("crash-report", "fatal-recovery", "electron", "ipcRenderer", "node:fs") if t in code]
    record(not hits, f"D6 不引用官方诊断实现、不做第二套崩溃采集（命中: {hits or '无'}）")

    return finish()


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for o, _ in RESULTS if o)
    bad = sum(1 for o, _ in RESULTS if not o)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
