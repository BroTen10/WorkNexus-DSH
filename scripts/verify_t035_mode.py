#!/usr/bin/env python
"""T-035 门禁：运行模式上下文与门控。

断言：
  D1  包结构齐备
  D2  类型构建通过（tsc）
  D3  单测通过（vitest）
  D4  判定：未登录/未选组织 personal；登录+有效组织 enterprise
  D5  四种场景：控制面不可达、组织失效、普通 personal、健康 enterprise
  D6  负向：无手工 mode 开关；无官方数据回滚/删除/企业数据复制

用法：python scripts/verify_t035_mode.py
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
PKG = REPO / "packages" / "host-core"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = ["package.json", "tsconfig.json", "src/mode.ts", "src/event-bus.ts",
            "src/index.ts", "test/mode.test.ts", "test/event-bus.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"D1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"D2 类型构建退出码 {tsc.returncode}"
           + ("" if tsc.returncode == 0 else f"（{tsc.stdout.strip()[:160]}）"))

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [line.strip() for line in (vit.stdout or "").splitlines() if "Tests" in line]
    record(vit.returncode == 0, f"D3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    probe = r"""
import('./dist/index.js').then(m=>{
  const org={signedIn:true,organizationId:'org-1',organizationContextValid:true,controlPlaneReachable:true};
  const personal=m.createModeContext({signedIn:false,organizationId:null});
  const signedNoOrg=m.createModeContext({signedIn:true,organizationId:null});
  const enterprise=m.createModeContext(org);
  const cpDown=m.createModeContext({...org,controlPlaneReachable:false});
  const orgBad=m.createModeContext({...org,organizationContextValid:false});
  console.log(JSON.stringify({
    personal:personal.mode,personalEntry:m.enterpriseEntryVisible(personal),personalCp:m.controlPlaneConnectionAllowed(personal),
    signedNoOrg:signedNoOrg.mode,
    enterprise:enterprise.mode,enterpriseEntry:m.enterpriseEntryVisible(enterprise),enterpriseCp:m.controlPlaneConnectionAllowed(enterprise),
    enterpriseGovernance:m.pluginGovernanceStrength(enterprise),enterpriseOwner:m.dataOwnership(enterprise),
    cpDown:cpDown.mode,cpDownDegraded:cpDown.degraded,cpDownReason:cpDown.degradationReason,cpDownEntry:m.enterpriseEntryVisible(cpDown),
    cpDownNotice:cpDown.notices.join(''),cpDownSession:cpDown.capabilities.officialSessionAvailable,
    orgBad:orgBad.mode,orgBadDegraded:orgBad.degraded,orgBadReason:orgBad.degradationReason,orgBadOwner:m.dataOwnership(orgBad)
  }));
}).catch(e=>console.log(JSON.stringify({error:String(e)})))
"""
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    record(
        info.get("personal") == "personal" and info.get("signedNoOrg") == "personal"
        and info.get("enterprise") == "enterprise",
        f"D4 判定规则（personal={info.get('personal')}，signedNoOrg={info.get('signedNoOrg')}，enterprise={info.get('enterprise')}）",
    )
    record(
        info.get("personalEntry") is False and info.get("personalCp") is False
        and info.get("enterpriseEntry") is True and info.get("enterpriseCp") is True
        and info.get("enterpriseGovernance") == "strict" and info.get("enterpriseOwner") == "organization",
        "D5a 门控：入口、控制面、治理强度与数据归属",
    )
    record(
        info.get("cpDown") == "enterprise" and info.get("cpDownDegraded") is True
        and info.get("cpDownReason") == "control-plane-unreachable"
        and info.get("cpDownEntry") is False
        and info.get("cpDownNotice", "").find("企业控制面不可达") >= 0
        and info.get("cpDownSession") is True,
        "D5b 控制面不可达：企业降级但 DSH 会话可用",
    )
    record(
        info.get("orgBad") == "personal" and info.get("orgBadDegraded") is True
        and info.get("orgBadReason") == "organization-context-invalid"
        and info.get("orgBadOwner") == "local",
        "D5c 组织上下文失效：退回个人且数据本地归属",
    )

    src = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in ("mode.ts", "index.ts"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [t for t in ("forceMode", "setMode", "rollbackOfficialData", "deleteOfficialData", "copyEnterpriseDataToLocal") if t in code]
    record(not hits, f"D6 无手工开关；无官方数据回滚/删除；无企业数据本地复制（命中: {hits or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
