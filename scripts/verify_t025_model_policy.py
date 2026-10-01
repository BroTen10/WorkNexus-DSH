#!/usr/bin/env python
"""T-025 门禁：企业凭据与模型策略对齐。

断言：
  M1  bundle 扩展齐备（model-policy.js + exports + patch 行）
  M2  负向：企业侧无第二套凭据存储（无凭据落盘/系统钥匙串/加密存储调用）
  M3  只读凭据事实：真实执行——只接受布尔事实，密钥形输入一律拒绝，返回值不含密钥
  M4  模型策略：预置默认 + org/space 下发 + 可用清单过滤 + 不可用时回落官方默认且不阻塞
  M5  负向：不接管官方模型配置页（上游差异集 = 差异集 01 品牌 11 + 差异集 02 打包集成新增 2）
  M6  明文凭据扫描（仓库与文档，脱敏测试夹具与上游差异集补丁除外）
  M7  真实装配：参照 dsh 组合树含企业模型策略行，且模块可真实 import 与自述
  M8  回归：T-023 门禁（patch 新增一行后仍全绿）
  M9  交付说明六段齐备 + 真机项已登记

用法：python scripts/verify_t025_model_policy.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
BUNDLE = REPO / "bundles" / "ent-core"
MODULE = BUNDLE / "model-policy.js"
DOC = REPO / "docs" / "企业凭据与模型策略_T-025.md"
WORK = REPO / ".dsh-check" / "t025"
PROFILE = "ent"
BUNDLE_NAME = "@worknexus/ent-core"
POLICY_ROW = "ent-core-model-policy"
POLICY_NAME = "@worknexus/ent-core/model-policy"

CREDENTIAL_STORAGE_TOKENS = [
    "credentials.yaml",
    ".credentials.",
    "keytar",
    "safeStorage",
    "wincred",
    "CredRead",
    "DPAPI",
    "createCipheriv",
]

SECRET_SCAN_ALLOW = [
    "packages/ent-diagnostics/test/",
    "scripts/verify_t026_diagnostics.py",
    # 本门禁自带「密钥形输入」负向夹具（用于证明拒绝路径），夹具值全部是合成串
    "scripts/verify_t025_model_policy.py",
    # T-028 起：合成夹具与「凭据不外泄 / 脱敏」用例需要出现密钥形字符串，均为构造值
    "packages/host-core/test/identity.test.ts",
    "plugins/knowledge/test/",
    "plugins/docgraph/test/",
    "plugins/market/test/",
    "patches/",
]

# `sk-` 前必须是词边界（避免 CSS 类名片段如 `risk-display` 误报）
SECRET_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{6,}|Bearer [A-Za-z0-9._-]{6,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)

PROBE = """\
const mod = await import(process.env.T025_MODULE)
const out = {}
const capture = (name, fn) => {
  try { out[name] = { ok: true, value: fn() } }
  catch (error) { out[name] = { ok: false, error: String((error && error.message) || error) } }
}
capture('describe', () => mod.describe())
capture('fact', () => mod.resolveCredentialFact({ hasUsableCredential: true, credentialRefs: ['DEEPSEEK_API_KEY'] }))
capture('fact-frozen', () => Object.isFrozen(mod.resolveCredentialFact({ hasUsableCredential: false })))
capture('reject-key-value', () => mod.resolveCredentialFact({ apiKey: 'sk-abcdef1234567890' }))
capture('reject-non-boolean', () => mod.resolveCredentialFact({ hasUsableCredential: 'yes' }))
capture('reject-secret-ref', () => mod.resolveCredentialFact({ hasUsableCredential: true, credentialRefs: ['sk-abcdef1234567890'] }))
capture('default', () => mod.resolveModelPolicy({}))
capture('organization', () => mod.resolveModelPolicy({ organization: { allowedModels: ['m-org'], defaultModel: 'm-org' } }))
capture('space-wins', () => mod.resolveModelPolicy({
  organization: { allowedModels: ['m-org'], defaultModel: 'm-org' },
  space: { allowedModels: ['m-space'], defaultModel: 'm-space' } }))
capture('filtered', () => mod.resolveModelPolicy({
  space: { allowedModels: ['m-a', 'm-b'] }, availableModels: ['m-b', 'm-c'] }))
capture('no-allowed-model', () => mod.resolveModelPolicy({
  space: { allowedModels: ['m-a'] }, availableModels: ['m-z'], officialDefaultModel: 'official-default' }))
capture('default-not-allowed', () => mod.resolveModelPolicy({
  space: { allowedModels: ['m-a', 'm-b'], defaultModel: 'm-z' }, officialDefaultModel: 'm-b' }))
capture('invalid-layer', () => mod.resolveModelPolicy({ organization: 'nope', officialDefaultModel: 'official-default' }))
capture('unknown-input-key', () => mod.resolveModelPolicy({ credential: 'sk-abcdef1234567890' }))
capture('reject-secret-model-id', () => mod.resolveModelPolicy({ space: { defaultModel: 'sk-abcdef1234567890' } }))
console.log('T025_PROBE=' + JSON.stringify(out))
"""

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def finish() -> int:
    print("-" * 60)
    ok = sum(1 for flag, _ in RESULTS if flag)
    bad = sum(1 for flag, _ in RESULTS if not flag)
    print(f"结果: {ok} [OK] / {bad} [FAIL]")
    return 1 if bad else 0


def node(*args: str, cwd: Path | None = None, env: dict | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(["node", *args], cwd=str(cwd or REPO), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=timeout)


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def find_dsh() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    p = Path(appdata) / "ThirdPartyApp" / "prod" / "harness" / "profiles" / "node_modules"
    p = p / "@deepseek-ai" / "dsh" / "lib" / "bin.js"
    return p if p.exists() else None


def source_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.exists():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        if path.suffix in {".js", ".ts", ".mjs", ".json", ".yml", ".yaml"}:
            out.append(path)
    return out


def run_probe() -> dict:
    probe_file = WORK / "probe.mjs"
    WORK.mkdir(parents=True, exist_ok=True)
    probe_file.write_text(PROBE, encoding="utf-8")
    env = dict(os.environ, T025_MODULE=MODULE.as_uri())
    result = node(str(probe_file), env=env)
    for line in (result.stdout or "").splitlines():
        if line.startswith("T025_PROBE="):
            return json.loads(line[len("T025_PROBE="):])
    raise RuntimeError(f"探针未产出结果: exit={result.returncode} stdout={result.stdout[-300:]} stderr={result.stderr[-300:]}")


def assemble(bin_js: Path) -> tuple[bool, str]:
    """在隔离 DSH_HOME 下装配参照 dsh，检查组合树含企业模型策略行。"""
    if WORK.exists():
        shutil.rmtree(WORK)
    prof = WORK / "profiles" / PROFILE
    scope = prof / "node_modules" / "@worknexus"
    scope.mkdir(parents=True, exist_ok=True)
    dest = scope / "ent-core"
    try:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dest), str(BUNDLE)],
                       capture_output=True, text=True, timeout=60, check=True)
    except Exception:
        shutil.copytree(BUNDLE, dest, dirs_exist_ok=True)
    (prof / "package.json").write_text(json.dumps({
        "name": f"dsh-profile-{PROFILE}",
        "private": True,
        "dependencies": {BUNDLE_NAME: f"link:{BUNDLE.as_posix()}"},
        "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", BUNDLE_NAME], "patchReload": "live"}},
        "type": "module",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    env = dict(os.environ, DSH_HOME=str(WORK))
    run = subprocess.run(["node", str(bin_js), "--profile", PROFILE, "--dump-config"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         env=env, timeout=180)
    out = run.stdout or ""
    return run.returncode == 0 and POLICY_NAME in out, f"exit={run.returncode}"


def main() -> int:
    # ── M1 bundle 扩展 ──
    pkg = json.loads((BUNDLE / "package.json").read_text(encoding="utf-8"))
    exports = pkg.get("exports", {})
    patch_text = (BUNDLE / "cordis.patch.yml").read_text(encoding="utf-8")
    record(
        MODULE.exists()
        and exports.get("./model-policy") == "./model-policy.js"
        and f"- id: {POLICY_ROW}" in patch_text
        and f"'{POLICY_NAME}'" in patch_text,
        "M1 企业模型策略模块已落地（模块 + exports + patch 行）",
    )

    # ── M2 无第二套凭据存储 ──
    hits: list[str] = []
    for root in (REPO / "packages", REPO / "bundles", REPO / "plugins"):
        for path in source_files(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            for token in CREDENTIAL_STORAGE_TOKENS:
                if token in text:
                    hits.append(f"{path.relative_to(REPO).as_posix()}:{token}")
    record(not hits, f"M2 企业侧无第二套凭据存储（命中: {hits or '无'}）")
    write_calls = [
        p.relative_to(REPO).as_posix()
        for p in source_files(REPO / "bundles")
        if re.search(r"\b(?:writeFile|appendFile|createWriteStream)\b", p.read_text(encoding="utf-8", errors="replace"))
    ]
    record(not write_calls, f"M2 企业 bundle 内无任何落盘写入调用（命中: {write_calls or '无'}）")

    # ── M3 / M4 真实执行探针 ──
    probe = run_probe()
    fact = probe.get("fact", {})
    record(
        fact.get("ok") is True
        and fact["value"]["source"] == "official-credentials-service"
        and fact["value"]["hasUsableCredential"] is True
        and "sk-" not in json.dumps(fact["value"]),
        "M3 凭据事实只返回布尔 + 引用名（source=official-credentials-service，无密钥值）",
    )
    record(probe.get("fact-frozen", {}).get("value") is True, "M3 凭据事实为冻结对象（不可被就地改写）")
    rejects = ["reject-key-value", "reject-non-boolean", "reject-secret-ref"]
    rejected = [name for name in rejects if probe.get(name, {}).get("ok") is False]
    record(rejected == rejects, f"M3 密钥形/非布尔输入一律拒绝（{rejected}）")
    record(probe.get("unknown-input-key", {}).get("ok") is False, "M3 未知键（可能夹带密钥）被拒绝（fail closed）")
    secret_model = probe.get("reject-secret-model-id", {}).get("value", {})
    record(secret_model.get("source") == "official-default"
           and str(secret_model.get("reason", "")).startswith("invalid-policy"),
           "M3 密钥形模型 id 不被采纳（回落官方默认，reason 以 invalid-policy 开头）")

    default = probe.get("default", {}).get("value", {})
    org = probe.get("organization", {}).get("value", {})
    space = probe.get("space-wins", {}).get("value", {})
    filtered = probe.get("filtered", {}).get("value", {})
    no_allowed = probe.get("no-allowed-model", {}).get("value", {})
    not_allowed = probe.get("default-not-allowed", {}).get("value", {})
    invalid = probe.get("invalid-layer", {}).get("value", {})
    record(default.get("defaultModel") == "deepseek-chat" and default.get("blocked") is False,
           f"M4 预置默认策略 = {default.get('defaultModel')} / {default.get('allowedModels')}")
    record(org.get("defaultModel") == "m-org" and space.get("defaultModel") == "m-space",
           "M4 下发优先级 space > organization（两者均已实测）")
    record(filtered.get("allowedModels") == ["m-b"], f"M4 可用清单过滤生效 = {filtered.get('allowedModels')}")
    record(no_allowed.get("source") == "official-default" and no_allowed.get("blocked") is False
           and no_allowed.get("reason") == "no-allowed-model",
           "M4 清单为空 → 回落官方默认且不阻塞会话")
    record(not_allowed.get("defaultModel") == "m-b" and not_allowed.get("blocked") is False,
           "M4 默认模型不在清单内 → 回落官方默认模型")
    record(invalid.get("source") == "official-default" and invalid.get("blocked") is False,
           "M4 非法策略层 → 回落官方默认且不阻塞会话")

    # ── M5 不接管官方模型配置页 ──
    paths = sorted(set(
        [p.strip() for p in git("diff", "--name-only", "HEAD").splitlines() if p.strip()]
        + [p.strip() for p in git("ls-files", "--others", "--exclude-standard").splitlines() if p.strip()]
    ))
    # 差异集 02 新增 prepare-package-set.ts 与 project-manager.ts；04 新增 scripts 下 3 条；
    # 03 新增 packages/client/** 6 条（均命中本检查的 packages/ 前缀）+ T-107 S3 就地更新的
    # 16 条上游期望文件（14 个 tests/expected/*.txt + 2 个 spec）+ S5 的 apps/desktop/src/main.ts；
    # 05 新增 7 条（构建期标题常量 + 2 个 scripts spec + 插件安全文案 + 3 个 Web e2e 期望）。
    # 这些都不接管官方模型配置页。
    record(len(paths) == 81, f"M5 上游差异集条目数（01 品牌 12 + 02 新增 2 + 04 新增 3 + 03 新增 24 + 05 新增 7 + 06 新增 4 + 07 新增 23 + 08 新增 6，实测 {len(paths)}）")
    upstream_touch = [p for p in paths if p.startswith("packages/") or p.startswith("apps/desktop/src/")]
    # 品牌源码落点（反向断言用：必须全部仍在差异集内）
    brand_src = [
        "apps/desktop/src/locale.ts",
        "apps/desktop/src/project-manager.ts",
        "apps/desktop/src/main.ts",
        "packages/client/ui-brand-official/src/client/Brand.tsx",
        "packages/client/ui-brand-official/src/client/index.ts",
        "packages/client/ui-settings-account/src/client/locales.ts",
        "packages/client/ui-settings-account/src/client/locales/onboarding.ts",
        "packages/client/ui-settings-models/src/client/locales.ts",
        "packages/client/ui-sidebar-documentpreview/src/client/office/locales.ts",
        "packages/client/ui-plugin-manager/src/client/locales.ts",
    ]
    allowed_src = [
        *brand_src,
        # 差异集 03（T-107 S3，DC-7 / DS-3）：上游期望文件就地更新；目录前缀覆盖 14 个 expected/*.txt。
        "packages/client/ui-brand-official/tests/browser-plugin.client.spec.tsx",
        "packages/client/ui-settings-models/tests/welcome-notice.client.spec.tsx",
        "packages/client/ui-settings-account/tests/expected/",
        # 差异集 06（反馈入口企业站点化）：目标站点常量 + 其上游期望值。
        "packages/client/ui-settings-account/src/contact-config.ts",
        "packages/client/ui-settings-account/tests/contact-url.client.spec.ts",
        # 差异集 06 扩项（T-108 顺手同步）：上游包 README 的「飞书问卷」表述。
        "packages/client/ui-settings-account/README.md",
        "packages/client/ui-settings-account/README.zh.md",
        # 差异集 05（T-107 S6，决策人「按建议执行」）：插件安全文案的 Web e2e 期望值就地更新。
        "apps/web/tests/expected/plugin-install-github/mirror.expected.md",
        "apps/web/tests/expected/plugin-install-cancel/cancelled.expected.md",
        "apps/web/tests/expected/plugin-install-github/another-way.expected.md",
    ]
    unexpected_src = [p for p in upstream_touch
                      if not any(p == a or p.startswith(a) for a in allowed_src)]
    # 反向断言：品牌源码 10 条必须仍在差异集内，避免允许清单退化为「放行一切」。
    missing_src = [a for a in brand_src if a not in upstream_touch]
    record(not unexpected_src and not missing_src,
           f"M5 未触及官方模型配置实现（越界 src 命中: {unexpected_src or '无'}；缺失品牌落点: {missing_src or '无'}）")
    desc = probe.get("describe", {}).get("value", {})
    record(desc.get("takesOverOfficialModelSettings") is False,
           "M5 模块自述声明不接管官方模型配置页（takesOverOfficialModelSettings=false）")

    # ── M6 明文凭据扫描 ──
    tracked = subprocess.run(["git", "ls-files"], cwd=str(REPO), capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.splitlines()
    leaked: list[str] = []
    for rel in tracked:
        if rel.startswith("repos/") or any(rel.startswith(prefix) for prefix in SECRET_SCAN_ALLOW):
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        if SECRET_PATTERN.search(path.read_text(encoding="utf-8", errors="replace")):
            leaked.append(rel)
    record(not leaked, f"M6 仓库与文档无明文凭据（命中: {leaked or '无'}）")

    # ── M7 真实装配 ──
    bin_js = find_dsh()
    if bin_js is None:
        record(False, "M7 参照 dsh 不可用")
    else:
        assembled, detail = assemble(bin_js)
        record(assembled, f"M7 组合树含企业模型策略行（{detail}）")
    record(desc.get("ok") is True
           and desc.get("storesCredentials") is False
           and desc.get("implementsCredentialStore") is False
           and desc.get("blockedOnPolicyFailure") is False,
           f"M7 模块自述：不存储凭据 / 不实现凭据存储 / 策略失败不阻塞（{desc.get('credentialSource')}）")

    # ── M8 T-023 回归 ──
    reg = subprocess.run([sys.executable, str(REPO / "scripts" / "verify_t023_bundle.py")],
                         cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=900)
    tail = [line for line in (reg.stdout or "").splitlines() if line.startswith("结果:")]
    record(reg.returncode == 0, f"M8 T-023 门禁回归（{' / '.join(tail) or '无输出'}）")

    # ── M9 交付说明 ──
    sections = ["## 1. 结论先行", "## 2. 改动清单", "## 3. 验证证据表",
                "## 4. 未验证项与边界", "## 5. 复现命令", "## 6. 下一步"]
    doc = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    missing = [section for section in sections if section not in doc]
    record(not missing, f"M9 交付说明六段齐备（缺: {missing or '无'}）")
    record("需真机复核" in doc and "明文" in doc, "M9 真机项（模型可切换 / Key 不出现在明文日志）已登记")

    return finish()


if __name__ == "__main__":
    raise SystemExit(main())
