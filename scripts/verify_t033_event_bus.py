#!/usr/bin/env python
"""T-033 门禁：企业事件通道薄适配层。

断言：
  H1  包结构齐备
  H2  类型构建通过（tsc）
  H3  单测通过（vitest）
  H4  运行时：只向官方 Context 注册 ent.* topic；发布携带 source
  H5  运行时：订阅者异常隔离和退订生效
  H6  运行时：白名单外 topic 不注册、不发布
  H7  负向：不维护第二套事件总线 / 队列

用法：python scripts/verify_t033_event_bus.py
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
    need = ["package.json", "tsconfig.json", "src/event-bus.ts", "src/index.ts", "test/event-bus.test.ts"]
    missing = [f for f in need if not (PKG / f).exists()]
    record(not missing, f"H1 包结构齐备（缺: {missing or '无'}）")

    tsc = node(str(PKG / "node_modules" / "typescript" / "bin" / "tsc"), "-p", "tsconfig.json", cwd=PKG)
    record(tsc.returncode == 0, f"H2 类型构建退出码 {tsc.returncode}"
           + ("" if tsc.returncode == 0 else f"（{tsc.stdout.strip()[:160]}）"))

    vit = node(str(PKG / "node_modules" / "vitest" / "vitest.mjs"), "run", cwd=PKG)
    tail = [line.strip() for line in (vit.stdout or "").splitlines() if "Tests" in line]
    record(vit.returncode == 0, f"H3 单测退出码 {vit.returncode}（{' / '.join(tail)}）")

    probe = r"""
import('./dist/index.js').then(m=>{
  const registered=[]; const emitted=[]; const listeners=new Map();
  const official={
    on(topic, handler){registered.push(topic); const l=listeners.get(topic)||[]; l.push(handler); listeners.set(topic,l); return ()=>{listeners.set(topic,(listeners.get(topic)||[]).filter(x=>x!==handler))}},
    emit(topic,event){emitted.push(topic); for(const h of listeners.get(topic)||[]) h(event)}
  };
  const errors=[]; const seen=[];
  const bus=m.createEnterpriseEventChannel({official,onError:x=>errors.push(x.error instanceof Error?x.error.message:String(x.error))});
  bus.subscribe('ent.identity.changed',()=>{throw new Error('bad subscriber')});
  bus.subscribe('ent.identity.changed',e=>seen.push(e.source));
  const event={topic:'ent.identity.changed',occurredAt:'2026-09-29T00:00:00.000Z',actorUserId:'u1',organizationId:'o1',payload:{},source:'probe'};
  bus.publish(event);
  const off=bus.subscribe('ent.space.switched',()=>seen.push('should-not-run'));
  off();
  bus.publish({...event,topic:'ent.space.switched',source:'off'});
  let whitelist=false;
  try{bus.subscribe('official.topic',()=>{})}catch{whitelist=true}
  let publishBlocked=false;
  try{bus.publish({...event,topic:'official.topic'})}catch{publishBlocked=true}
  console.log(JSON.stringify({registered,emitted,seen,errors,whitelist,publishBlocked,allowed:bus.allowedTopics().length}));
}).catch(e=>console.log(JSON.stringify({error:String(e)})))
"""
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    record(
        info.get("registered") == ["ent.identity.changed", "ent.identity.changed", "ent.space.switched"]
        and info.get("emitted") == ["ent.identity.changed", "ent.space.switched"]
        and info.get("allowed") == 6,
        f"H4 只注册 ent.* topic 且复用官方 emit（registered={info.get('registered')}，emitted={info.get('emitted')}）",
    )
    record(
        info.get("seen") == ["probe"]
        and info.get("errors") == ["bad subscriber"],
        f"H5 订阅者异常隔离与退订生效（seen={info.get('seen')}，errors={info.get('errors')}）",
    )
    record(
        info.get("whitelist") is True
        and info.get("publishBlocked") is True,
        "H6 白名单外 topic 不注册、不发布",
    )

    src = "\n".join((PKG / "src" / f).read_text(encoding="utf-8") for f in ("event-bus.ts", "index.ts"))
    code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    code = re.sub(r"(?m)^\s*//.*$", "", code)
    hits = [t for t in ("new Map", "new Set", "setTimeout", "queue", "EventEmitter") if t in code]
    record(not hits, f"H7 不维护第二套事件总线 / 队列（命中: {hits or '无'}）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
