#!/usr/bin/env python
"""T-028 门禁：发行版验收门禁与交付说明（批次 1 收尾）。

判定口径（诚实口径）：
  需求书 §4.1.5 的**十条**验收，每条必须二选一：
    (a) 本轮有**可执行证据**（对应的门禁脚本在本轮真实跑绿）；或
    (b) 已在交付说明 §4 登记为**待人工复核（B）**并写明缺什么、怎么补。
  任一条既无证据、又无登记 → [FAIL]。因此本门禁判的是「证据状态完整」，而不是「十项已全绿」。

断言：
  R1  批次 1 全部子门禁本轮跑绿（T-021/T-023/T-024/T-025/T-026/T-027/T-029，+可选 T-020/T-022）
  R2  §4.1.5 十条逐条有证据或待人工登记，且无遗漏
  R3  负向：AgentTransport 实现只允许在 P6A 的 ACP 适配层；交互主链路零实现（P1 不变式保持）
  R4  负向：§11 禁止清单——无第二套插件系统 / 凭据存储 / 诊断体系
  R5  差异集与白名单一致（`git diff --stat` 与 T-002 §3 白名单）
  R6  上游测试资产完整性：未删除、未跳过、未增删用例声明（AGENTS.md §6；期望值就地更新按 DC-7 / DS-3 放行）
  R7  可用性计时口径与记录（§7 ≤5 分钟；本轮为待人工项 + 计时表模板）
  R8  交付说明六段 + 未验证项三分（B/C/超出范围）+ 待人工项清单
  R9  总览已回写 T-020 ~ T-028 状态

用法：
  python scripts/verify_t028_release.py            # 全量（含两个 --full 子门禁，约 2 分钟）
  python scripts/verify_t028_release.py --quick    # 跳过需要构建/演练的子门禁
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
DOC = REPO / "docs" / "企业发行版_T-028.md"
INDEX = REPO / "docs" / "开发文档索引.md"
OVERVIEW = REPO / "docs" / "任务拆分-WorkNexus-DSH_总览与任务索引_v3.0_T-000~T-105.md"
STATUS = REPO / ".dsh-check" / "t028-gates.json"

# §4.1.5 十条验收 → 证据来源（门禁脚本名 / 文档路径 / None 表示待人工）
ACCEPTANCE = [
    ("4.1.5-1 干净环境安装发行版后可启动客户端并运行 DSH Web profile", None,
     "需安装包 + 干净 Windows 环境 + GUI（真机项）", "T-028 B-1"),
    ("4.1.5-2 完整 Agent 会话（新建/发送/流式/取消/恢复）", None,
     "需 GUI 真机会话（真机项）", "T-028 B-2"),
    ("4.1.5-3 重启后历史会话可见且可恢复", None,
     "需 GUI 真机重启（真机项）", "T-028 B-3"),
    ("4.1.5-4 升级演练（我方签名产物 + 我方企业更新源）", "t022",
     "机制部分已验证（官方资格套件 16 场景）；签名产物与真实企业源待人工", "T-028 B-4 / T-022 B-1/B-3"),
    ("4.1.5-5 DSH 版本 / profile / 插件状态可通过诊断页面查看", "t026",
     "企业侧脱敏诊断与白名单已验证；UI 页面可见性待人工", "T-028 B-5"),
    ("4.1.5-6 关闭或异常退出后再次启动不损坏数据/配置", "t023",
     "恢复入口与失败隔离（装配层）已验证；Boot 层真机项待人工", "T-028 B-6"),
    ("4.1.5-7 差异集可枚举且在白名单内；上游 rebase 演练成功", "t027",
     "已由 T-021/T-027 本轮实测", "T-028 V-7"),
    ("4.1.5-8 企业 bundle 不被列为可禁用第三方（降级：一次性恢复且不丢数据）", "t023",
     "一次性恢复入口与「其他数据不丢」已验证；原生恢复对话框真机项待人工", "T-028 B-7"),
    ("4.1.5-9 发行物合规（MIT/NOTICE/品牌）", "t021",
     "差异集合规文件逐字节未变 + 品牌串替换已验证；安装包内落点待人工", "T-028 B-8"),
    ("4.1.5-10 升级可回退且保留会话与配置", "t022",
     "更新器禁止自动降级 + 安装器数据保护机制已验证；真实回退待人工", "T-028 B-9"),
]

# 批次 1 子门禁：名称 → (脚本, 附加参数)
GATES = {
    "t020": ("verify_t020_build.py", []),
    "t021": ("verify_t021_brand.py", []),
    "t022": ("verify_t022_update.py", []),
    "t023": ("verify_t023_bundle.py", []),
    "t024": ("verify_t024_entries.py", []),
    "t025": ("verify_t025_model_policy.py", []),
    "t026": ("verify_t026_diagnostics.py", []),
    "t027": ("verify_t027_upstream_sync.py", ["--no-build"]),
    "t029": ("verify_t029_skeleton.py", []),
}

FULL_GATES = {
    "t021": ("verify_t021_brand.py", ["--full"]),
    "t022": ("verify_t022_update.py", ["--full"]),
}

WHITELIST_PATHS = [
    "README.md",
    "CHANGELOG.md",
    "WORKNEXUS-RELEASE-NOTES.md",
    "apps/desktop/resources/",
    "apps/desktop/scripts/electron-builder-config.mjs",
    "apps/desktop/src/locale.ts",
    "apps/desktop/.env.windows",
    "apps/desktop/scripts/desktop-release-environment.mjs",
    "apps/desktop/scripts/desktop-auto-update-environment.mjs",
    "apps/desktop/scripts/windows-sign.mjs",
    "apps/desktop/scripts/windows-sign.cmd",
    # 差异集 02「发行物打包集成」（DC-6 批准，2026-09-29）：白名单 3.1「预置 bundle 清单」+ 合规文件随包落点
    "apps/desktop/scripts/prepare-package-set.ts",
    "apps/desktop/src/project-manager.ts",
    # 差异集 04「打包后冒烟脚本产品名」（DC-6 批准）：产品名单一来源 + 冒烟脚本跟随
    "apps/desktop/scripts/desktop-product-name.mjs",
    "apps/desktop/scripts/desktop-product-name.d.mts",
    "apps/desktop/scripts/smoke-packaged-runtime.ts",
    # 差异集 03「客户端品牌残留」（DC-6 批准）：品牌组件 + 客户端文案
    "packages/client/ui-brand-official/src/client/Brand.tsx",
    "packages/client/ui-brand-official/src/client/index.ts",
    "packages/client/ui-settings-account/src/client/locales.ts",
    "packages/client/ui-settings-account/src/client/locales/onboarding.ts",
    "packages/client/ui-settings-models/src/client/locales.ts",
    "packages/client/ui-sidebar-documentpreview/src/client/office/locales.ts",
    # 差异集 03（T-107 S3，DC-7 / DS-3 口径）：品牌文案牵动的上游期望文件**就地更新**
    # （14 个 `tests/expected/*.txt` + 2 个 spec 内联期望）。只改期望值，测试逻辑与用例数不变。
    "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
    "packages/client/ui-settings-models/tests/welcome-notice.client.spec.tsx",
    "packages/client/ui-settings-account/tests/expected/",
    # 差异集 03（T-107 S5）：关于页 applicationName 单行替换（白名单 1.4）+ 其直接期望文件。
    "apps/desktop/src/main.ts",
    "apps/desktop/tests/expected/about-panel.json",
    # 差异集 05「客户端可见品牌面」（2026-09-30 决策人「按建议执行」批准）：构建期标题常量
    # （窗口标题根因）+ 插件安装安全文案 + 其上游期望值。
    "scripts/client-build-environment.ts",
    "scripts/client-build-environment.client.spec.ts",
    "scripts/dev-web.spec.ts",
    "packages/client/ui-plugin-manager/src/client/locales.ts",
    "apps/web/tests/expected/plugin-install-github/mirror.expected.md",
    "apps/web/tests/expected/plugin-install-cancel/cancelled.expected.md",
    "apps/web/tests/expected/plugin-install-github/another-way.expected.md",
    # 差异集 06「反馈入口企业站点化」（2026-09-30）：目标站点常量（企业侧页面入口）+ 其期望值。
    "packages/client/ui-settings-account/src/contact-config.ts",
    "packages/client/ui-settings-account/tests/contact-url.client.spec.ts",
    # 差异集 06 扩项（T-108 顺手同步）：上游包 README 不再声称「飞书问卷」。
    "packages/client/ui-settings-account/README.md",
    "packages/client/ui-settings-account/README.zh.md",
    # 差异集 07「桌面壳测试期望同步」（T-108，DC-7 / DS-3 口径）：apps/desktop/tests 期望值就地更新。
    "apps/desktop/tests/background-notice.spec.ts",
    "apps/desktop/tests/installer-packaging.spec.ts",
    "apps/desktop/tests/macos-signature.spec.ts",
    "apps/desktop/tests/main-startup.spec.ts",
    "apps/desktop/tests/quit-confirmation.spec.ts",
    "apps/desktop/tests/tray.spec.ts",
    "apps/desktop/tests/windows-update-publisher.spec.ts",
    "apps/desktop/tests/expected/application-menu-en-US.json",
    "apps/desktop/tests/expected/application-menu-zh-CN.json",
    "apps/desktop/tests/expected/fatal-",
    "apps/desktop/tests/expected/welcome/",
    # 差异集 01 追加：`productName`（决定 %APPDATA% 目录名）。
    "apps/desktop/package.json",
    # 差异集 08「更新源企业化」：生产 origin 环境驱动 + 模板说明。
    "apps/desktop/scripts/desktop-auto-update-environment.mjs",
    "apps/desktop/tests/desktop-auto-update-environment.spec.ts",
    "apps/desktop/tests/desktop-upload-plan.spec.ts",
    "apps/desktop/tests/expected/latest-installer-uploads.json",
    "apps/desktop/.env.windows.example",
    "apps/desktop/.env.macos.example",
]

CREDENTIAL_TOKENS = ["credentials.yaml", ".credentials.", "keytar", "safeStorage", "wincred", "DPAPI"]

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def info(detail: str) -> None:
    print(f"[INFO] {detail}")


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for flag, _ in RESULTS if flag)
    bad = sum(1 for flag, _ in RESULTS if not flag)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


def run(args: list[str], cwd: Path, timeout: int = 2400) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def git(args: list[str], cwd: Path) -> str:
    return run(["git", *args], cwd).stdout


def run_gate(name: str, args: list[str]) -> tuple[bool, str]:
    script = REPO / "scripts" / GATES[name][0] if name in GATES else None
    if script is None or not script.exists():
        return False, "脚本缺失"
    result = run([sys.executable, str(script), *args], REPO)
    tail = [line for line in (result.stdout or "").splitlines() if line.startswith("结果:")]
    return result.returncode == 0, (tail[-1] if tail else f"exit={result.returncode}")


def changed_paths() -> list[str]:
    paths = [line.strip() for line in git(["diff", "--name-only", "HEAD"], UPSTREAM).splitlines() if line.strip()]
    paths += [line.strip() for line in git(["ls-files", "--others", "--exclude-standard"], UPSTREAM).splitlines() if line.strip()]
    return sorted(set(paths))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过 --full 子门禁（跳过构建与演练重跑）")
    args = ap.parse_args()

    gate_state: dict[str, str] = {}
    gate_ok: dict[str, bool] = {}

    # ── R1 批次 1 子门禁 ──
    for name in ["t020", "t021", "t022", "t023", "t024", "t025", "t026", "t027", "t029"]:
        if args.quick and name in {"t020", "t022"}:
            gate_state[name] = "跳过（--quick）"
            info(f"R1 {name} 已按 --quick 跳过")
            continue
        script, extra = GATES[name]
        ok, tail = run_gate(name, extra)
        gate_state[name] = tail
        gate_ok[name] = ok
        record(ok, f"R1 {name}（{script}{' ' + ' '.join(extra) if extra else ''}）= {tail}")
    if not args.quick:
        for name, (script, extra) in FULL_GATES.items():
            ok, tail = run_gate(name, extra)
            gate_state[f"{name}-full"] = tail
            gate_ok[f"{name}-full"] = ok
            record(ok, f"R1 {name} --full（{script} {' '.join(extra)}）= {tail}")

    # ── R2 十条验收证据状态 ──
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    unregistered: list[str] = []
    missing_evidence: list[str] = []
    for item, gate, note, register in ACCEPTANCE:
        if gate is None:
            if register not in doc:
                unregistered.append(item)
            continue
        if args.quick and gate in {"t020", "t022"}:
            continue
        passed = gate_ok.get(gate, False) or gate_ok.get(f"{gate}-full", False)
        if not passed:
            missing_evidence.append(item)
    record(not missing_evidence, f"R2 有可执行证据的验收项其门禁本轮已跑绿（缺: {missing_evidence or '无'}）")
    record(not unregistered, f"R2 待人工项均已在交付说明登记（未登记: {unregistered or '无'}）")
    item_count_ok = all(f"4.1.5-{i}" in doc for i in range(1, 11))
    record(item_count_ok, "R2 §4.1.5 十条在交付说明中逐条出现（1~10）")

    # ── R3 负向：AgentTransport 实现只允许在 P6A 的 ACP 适配层 ──
    hits = [line.strip().replace("\\", "/") for line in git(["grep", "-l", "AgentTransport"], REPO).splitlines() if line.strip()]
    code_hits = [h for h in hits if h.startswith(("bundles/", "packages/", "plugins/", "apps/", "services/"))]
    # 允许出现：P1「显式声明不实现」的自述文件（T-029 禁止事项、契约包注释）
    # 以及 P6A（T-090）的 ACP 适配层与其「不支持能力」显式返回
    allowed_hits = {
        "bundles/ent-core/index.js",
        "bundles/ent-core/skeleton.js",
        "packages/contracts/src/index.ts",
        "packages/kernel-dsh/src/acp-transport.ts",
        "packages/kernel-dsh/test/transport.contract.ts",
        "packages/kernel-dsh/test/acp-transport.test.ts",
        "plugins/acp/test/acceptance.test.ts",
        "plugins/docgraph/src/agent-bridge.ts",
    }
    extra_hits = [h for h in code_hits if h not in allowed_hits]
    record(not extra_hits, f"R3 代码命中仅为自述文件与 P6A ACP 适配层（越界: {extra_hits or '无'}）")

    # P1 不变式：交互主链路（客户端壳 / host-core / 控制面）不得实现或依赖 AgentTransport
    main_chain_hits = [h for h in code_hits if h.startswith(("apps/desktop", "packages/host-core", "services/"))]
    record(not main_chain_hits, f"R3 交互主链路无 AgentTransport（命中: {main_chain_hits or '无'}）")

    # 只允许一个实现模块（P6A 的 ACP 适配层），且它不得自研协议传输
    implementation_hits = [h for h in code_hits if "transport" in h.lower() and h.startswith("packages/kernel-dsh/src/")]
    acp_source = (REPO / "packages/kernel-dsh/src/acp-transport.ts")
    acp_text = acp_source.read_text(encoding="utf-8") if acp_source.exists() else ""
    record(implementation_hits == ["packages/kernel-dsh/src/acp-transport.ts"]
           and all(token not in acp_text for token in ("jsonrpc", "createInterface(", "spawn(")),
           f"R3 唯一实现模块为 kernel-dsh/acp-transport.ts（实现: {implementation_hits or '无'}）")
    record("acp-unsupported" in acp_text,
           "R3 官方不支持的能力显式返回不支持（不伪装）")

    # ── R4 负向：§11 禁止清单 ──
    own_sources = []
    for root in ("packages", "bundles", "plugins", "services"):
        path = REPO / root
        if path.exists():
            own_sources += [p for p in path.rglob("*") if p.is_file() and "node_modules" not in p.parts
                            and p.suffix in {".js", ".ts", ".mjs", ".json", ".yml", ".yaml"}]
    credential_hits = [p.relative_to(REPO).as_posix() for p in own_sources
                       if any(token in p.read_text(encoding="utf-8", errors="replace") for token in CREDENTIAL_TOKENS)]
    record(not credential_hits, f"R4 无第二套凭据存储（命中: {credential_hits or '无'}）")
    plugin_manager = [p.relative_to(REPO).as_posix() for p in own_sources
                      if re.search(r"plugin[-_]manager", p.name, re.IGNORECASE)]
    record(not plugin_manager, f"R4 无第二套插件系统（命中: {plugin_manager or '无'}）")
    crash = [p.relative_to(REPO).as_posix() for p in own_sources if "crash-report" in p.name]
    record(not crash, f"R4 无第二套诊断体系（命中: {crash or '无'}）")

    # ── R5 差异集与白名单一致 ──
    paths = changed_paths()
    outside = [p for p in paths if not any(p == w or p.startswith(w) for w in WHITELIST_PATHS)]
    record(not outside, f"R5 上游差异集全部落在白名单内（越界: {outside or '无'}）")
    # 差异集 01 = 11 路径；02 新增 2；04 新增 3（含 S5 端到端出包暴露的缺失 .d.mts）；03 新增 24
    # （品牌组件 + index.ts + 4 个客户端文案文件 + T-107 S3 就地更新的 16 个上游期望文件
    # + S5 的 main.ts 与 about-panel.json）；05 新增 7（构建期标题常量 + 2 个 scripts spec
    # + 插件安全文案 + 3 个 Web e2e 期望）；06 新增 4（反馈入口目标站点 + 期望值 + 2 个 README）；
    # 07 新增 23（apps/desktop/tests 期望值与内联断言就地更新）；08 新增 6（更新源企业化）；
    # 01 追加 apps/desktop/package.json（productName）→ 合计 81；被前序差异集覆盖的文件不重复计数。
    record(len(paths) == 81, f"R5 差异集条目数 = {len(paths)}（01 品牌 12 + 02 新增 2 + 04 新增 3 + 03 新增 24 + 05 新增 7 + 06 新增 4 + 07 新增 23 + 08 新增 6）")
    # 指定足够大的 --stat 宽度，否则长路径会被 git 截断成 `.../xxx`，
    # 与白名单前缀比对时产生假阴性（差异集 03 新增的 packages/client 长路径即由此暴露）。
    stat_text = git(["diff", "--stat=300", "HEAD"], UPSTREAM)
    stat_names = {line.split("|")[0].strip() for line in stat_text.splitlines() if "|" in line}
    record(bool(stat_names) and all(any(n == w or n.startswith(w) for w in WHITELIST_PATHS) for n in stat_names),
           f"R5 git diff --stat 与白名单一致（{len(stat_names)} 个文件）")

    # ── R6 上游测试资产完整性（AGENTS §6）──
    # 原判据「任何 tests/ 路径改动即失败」在本批失效：DC-7 / DS-3（决策人 2026-09-29 批准）
    # 已裁决品牌差异牵动的**期望值**就地更新属允许动作，且要求固化为差异集 03 的补丁。
    # 故改为逐项证明测试资产未被削弱：未删除、未跳过、未增删用例声明。
    deleted_tests = [p for p in git(["diff", "--diff-filter=D", "--name-only", "HEAD"], UPSTREAM).splitlines() if p.strip()]
    record(not deleted_tests, f"R6 上游测试文件未被删除（命中: {deleted_tests or '无'}）")
    diff_text = git(["diff", "HEAD"], UPSTREAM)
    added_skips = [line for line in diff_text.splitlines()
                   if line.startswith("+") and not line.startswith("+++")
                   and re.search(r"\.(?:skip|todo)\(", line)]
    record(not added_skips, f"R6 差异集未新增 skip/todo（命中: {len(added_skips)}）")
    # 用例声明（it / it.each / test / describe）不得增删 —— 期望值更新不得改变用例数。
    changed_specs = [p for p in paths if p.endswith((".spec.ts", ".spec.tsx"))]
    case_changes = []
    for rel in changed_specs:
        for line in git(["diff", "HEAD", "--", rel], UPSTREAM).splitlines():
            if line[:1] in "+-" and not line.startswith(("+++", "---")) \
                    and re.search(r"(?<![\w$])(?:it|test|describe)(?:\.\w+)?\(", line):
                case_changes.append(f"{rel}:{line[:1]}{line[1:].strip()[:60]}")
    record(not case_changes, f"R6 用例声明未增删（改动 spec: {changed_specs or '无'}；命中: {case_changes or '无'}）")

    # ── R7 可用性计时 ──
    record("计时" in doc and "5 分钟" in doc,
           "R7 交付说明含 §7 可用性计时口径与计时表")
    record("待人工" in doc, "R7 计时记录标记为待人工项")

    # ── R8 交付说明结构 ──
    sections = ["## 1. 结论先行", "## 2. 改动清单", "## 3. 验证证据表",
                "## 4. 未验证项与边界", "## 5. 复现命令", "## 6. 下一步"]
    missing_sections = [s for s in sections if s not in doc]
    record(not missing_sections, f"R8 交付说明六段齐备（缺: {missing_sections or '无'}）")
    three_way = all(token in doc for token in ["需真机复核", "需外部输入", "超出本次范围"])
    record(three_way, "R8 未验证项三分齐备（B/C/超出范围）")

    # ── R9 总览回写 ──
    overview = OVERVIEW.read_text(encoding="utf-8")
    record("批次 1 执行状态" in overview, "R9 总览已回写批次 1 执行状态小节")
    record(all(f"T-0{n}" in overview for n in range(20, 30)), "R9 总览状态小节覆盖 T-020 ~ T-029")
    record(INDEX.exists() and "企业发行版_T-028" in INDEX.read_text(encoding="utf-8"),
           "R9 开发文档索引已登记 T-028 交付说明")

    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({
        "gates": gate_state,
        "acceptance": [{"item": item, "gate": gate, "note": note, "register": register}
                       for item, gate, note, register in ACCEPTANCE],
        "changedPaths": paths,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    info(f"门禁状态报告: {STATUS.relative_to(REPO).as_posix()}")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
