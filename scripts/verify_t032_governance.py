#!/usr/bin/env python
"""T-032 门禁：企业治理挂接官方 plugin-manager。

断言：
  G1  包结构齐备
  G2  类型构建通过（tsc）
  G3  单测通过（vitest）
  G4  运行时：白名单内安装 allow 并审计；白名单外 deny
  G5  运行时：审计失败不阻塞 enable / disable / uninstall
  G6  运行时：official changed 事件映射不重写生命周期
  G7  负向：不实现 enable / disable / install / remove 权威操作

用法：python scripts/verify_t032_governance.py
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
UPSTREAM = REPO / "repos" / "deepseek-harness"

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    need = ["package.json", "tsconfig.json", "src/manifest.ts", "src/governance.ts",
            "src/index.ts", "test/manifest.test.ts", "test/governance.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"G1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"G2 类型构建退出码 {tsc.returncode}"
           + ("" if tsc.returncode == 0 else f"（{tsc.stdout.strip()[:160]}）"))

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [line.strip() for line in (vit.stdout or "").splitlines() if "Tests" in line]
    record(vit.returncode == 0, f"G3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    probe = r"""
import('./dist/index.js').then(async m=>{
  const audited=[];
  const allowHooks=m.createGovernanceHooks({whitelist:['worknexus.knowledge'],audit:e=>audited.push(e.action)});
  const denyHooks=m.createGovernanceHooks({whitelist:[],audit:()=>{}});
  const failing=m.createGovernanceHooks({whitelist:[],audit:()=>{throw new Error('audit down')}});
  const [allow,deny]=await Promise.all([
    allowHooks.onInstall({pluginId:'worknexus.knowledge',version:'1.0.0'}),
    denyHooks.onInstall({pluginId:'unknown.plugin',version:'1.0.0'}),
    failing.onEnable({pluginId:'p',version:'1'}),
    failing.onDisable({pluginId:'p',version:'1'}),
    failing.onUninstall({pluginId:'p',version:'1'}),
  ]);
  const events=[]; const registered=[]; const listeners=new Map();
  const official={on(topic,handler){registered.push(topic);listeners.set(topic,[handler]);return ()=>{}}};
  m.attachGovernanceHooks({official,hooks:{
    onInstall:e=>audited.push('plugin.install:'+e.pluginId),
    onEnable:async()=>{},
    onDisable:async()=>{},
    onUninstall:e=>events.push('uninstall'),
    onPluginOrBundleChanged:e=>events.push('changed:'+e.reason),
  }});
  const handler=listeners.get('plugin-manager/changed')[0];
  handler({reason:'install'}); handler({reason:'remove'}); handler({reason:'plugin'}); handler({reason:'bundle'});
  await new Promise(resolve=>setImmediate(resolve));
  console.log(JSON.stringify({allow,deny,audited,events,registered}));
  return {allow,deny,audited,events,registered};
}).catch(e=>({error:String(e)}))
"""
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    record(
        info.get("allow", {}).get("decision") == "allow"
        and info.get("deny", {}).get("decision") == "deny"
        and info.get("deny", {}).get("reason", "").find("whitelist") >= 0
        and info.get("audited", [])[0] == "plugin.install",
        f"G4 安装治理：allow={info.get('allow')}，deny={info.get('deny')}，audited={info.get('audited')}",
    )
    record(
        info.get("error") is None
        and info.get("events") == ["uninstall", "changed:plugin", "changed:bundle"]
        and info.get("registered") == ["plugin-manager/changed"],
        f"G5/G6 官方事件不阻塞；changed 映射={info.get('events')}",
    )

    src = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in ("manifest.ts", "governance.ts", "index.ts"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [t for t in ("enablePlugin", "disablePlugin", "installBundle", "removeBundle", "loadPlugin", "unloadPlugin") if t in code]
    record(not hits, f"G7 不实现插件启停 / 安装 / 卸载权威操作（命中: {hits or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
