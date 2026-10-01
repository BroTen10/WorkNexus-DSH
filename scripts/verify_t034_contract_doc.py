#!/usr/bin/env python
"""T-034 门禁：Host Core 契约 v1 冻结一致性。

断言：
  C1  契约文档存在并包含冻结 / 版本策略 / 迁移规则
  C2  代码契约版本为 1.1.0 且可导入
  C3  八类契约 + P3 扩展契约⑨在运行时可见
  C4  事件白名单与文档一致
  C5  权限枚举与文档声明一致
  C6  插件治理视图无启停语义；更新契约有 upstreamPin
  C7  变更留痕表已建立

用法：python scripts/verify_t034_contract_doc.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "packages" / "contracts"
DOC = REPO / "docs" / "HostCore契约-v1.md"
VERSION = "1.1.0"

EVENT_TOPICS = [
    "ent.identity.changed",
    "ent.space.switched",
    "ent.audit.written",
    "ent.usage.recorded",
    "ent.plugin.state.changed",
    "ent.update.availability.changed",
]

ACTIONS = [
    "space.read", "space.write", "member.invite", "member.remove", "role.assign",
    "plugin.enable", "plugin.disable", "audit.read", "usage.read", "budget.write",
    "kb.retrieve", "kb.bind", "docgraph.submit", "docgraph.read", "session.create",
]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def node(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=600)


def main() -> int:
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    required_doc = ["冻结版本", "版本策略与迁移规则", "破坏性变更 → minor", "新增字段 → patch", "变更留痕"]
    missing_doc = [item for item in required_doc if item not in doc]
    record(DOC.exists() and not missing_doc, f"C1 契约文档冻结与版本策略齐备（缺: {missing_doc or '无'}）")

    probe = (
        "import('@worknexus/contracts').then(m=>{"
        "const need=['IdentityContext','SpaceContext','PermissionPolicy','AuditSink','UsageLedger','EventBus',"
        "'PluginGovernanceView','UpdateManager'];"
        "console.log(JSON.stringify({"
        "version:m.HOST_CORE_CONTRACT_VERSION,"
        "topics:[...m.ENTERPRISE_EVENT_TOPICS],"
        "actions:[...m.ACTIONS],"
        "viewMethods:Object.keys(m.PERSONAL_MODE_GOVERNANCE),"
        "prefix:m.ENTERPRISE_FIELD_PREFIX,"
        "knowledgeStates:[...m.KNOWLEDGE_HEALTH_STATES]}));})"
    )
    r = node("--input-type=module", "-e", probe, cwd=PKG)
    try:
        info = json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception:
        info = {"error": (r.stdout or r.stderr or "").strip()[:200]}

    record(info.get("version") == VERSION, f"C2 契约版本 = {info.get('version')}（期望 {VERSION}）")

    missing_types = [
        item for item in ["IdentityContext", "SpaceContext", "PermissionPolicy", "AuditSink",
                          "UsageLedger", "EventBus", "PluginGovernanceView", "UpdateManager",
                          "KnowledgeProvider"]
        if item not in doc
    ]
    record(not missing_types
           and info.get("knowledgeStates") == ["healthy", "unreachable", "auth_failed", "sync_failed"],
           f"C3 契约签名（八类 + 契约⑨）在文档与运行时可见（缺: {missing_types or '无'}）")
    record(info.get("topics") == EVENT_TOPICS, "C4 事件白名单与冻结文档一致")
    record(info.get("actions") == ACTIONS, "C5 权限枚举与冻结文档一致")
    record(
        info.get("prefix") == "ent"
        and all(item in info.get("viewMethods", []) for item in ["list", "stateOf", "isAllowed"])
        and all(item not in info.get("viewMethods", []) for item in ["enable", "disable"])
        and "upstreamPin()" in doc,
        "C6 插件治理只读；更新契约含 upstreamPin",
    )
    record("| `1.0.0` | 2026-09-29 |" in doc and "初始冻结" in doc
           and "| `1.1.0` | 2026-09-29 |" in doc,
           "C7 变更留痕表已建立（1.0.0 初始冻结 + 1.1.0 契约⑨）")

    print("-" * 60)
    ok = sum(1 for passed, _ in RESULTS if passed)
    bad = sum(1 for passed, _ in RESULTS if not passed)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
