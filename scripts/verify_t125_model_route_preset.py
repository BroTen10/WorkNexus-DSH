#!/usr/bin/env python
"""T-125 门禁：发行版默认模型路由预置（差异集 02/07/10 扩项）。

断言：
  P1  工作树 seam 就位：新模块导出预置常量与两个函数；`applyRelease` 在 profile 锁内、
      以 try/catch 调用它（写失败不阻断启动）
  P2  行为探针（真实 tsx 执行上游模块）：官方模板 `[]` 被换成块序列并带上 hub 路由与默认模型 /
      幂等（二次调用不写盘、字节不变）/ 机器已有自己的行则整体让位 /
      追加不改既有字节 / 映射根与缺失用户层拒绝写盘 / 产物无密钥
  P3  无密钥：模块、探针产物、差异集补丁里都不出现 `sk-` 字面量；模块不碰官方凭据文件
  P4  差异集口径：02 = 3 文件、07 = 24 文件、10 = 1 新增文件不变；上游差异集条目数 120 不变；
      本次改动的 3 个文件都已在既有枚举内（不新增条目）
  P5  上游 spec 只就地改期望：`project-manager.spec.ts` 的用例声明（describe/it）增删为 0
  P6  文档齐备：交付说明六段 + 差异集清单/开发文档索引/当日账本均已登记
  P7  负向：`packages/boot/**` 未被改动（N-3 加载顺序不动）
  P8  产物（存在时）：`win-unpacked/resources/app.asar` 内含默认路由标记
      （`hub.example.com` / `enterprise-hub` / `ENTERPRISE_HUB_API_KEY`），且不含任何密钥值
  P9  装机态（`--launch`）：以**隔离 `DSH_HOME` + 隔离 `--user-data-dir`** 起一次安装态客户端，
      断言新 profile 的用户层被自动补上默认路由两条行（新装机默认的端到端判据）

用法：python scripts/verify_t125_model_route_preset.py [--launch]
退出码：全部通过为 0；任一 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
UPSTREAM = REPO / "repos" / "deepseek-harness"
PATCHES = REPO / "patches"
MODULE = "apps/desktop/src/profile-bundle-backfill.ts"
MANAGER = "apps/desktop/src/project-manager.ts"
SPEC = "apps/desktop/tests/project-manager.spec.ts"
DELIVERY_DOC = REPO / "docs" / "发行版默认模型路由_T-125.md"
LEDGER = REPO / "docs" / "执行账本-2026-10-15.md"
INDEX = REPO / "docs" / "开发文档索引.md"
DIFFSET_REGISTRY = REPO / "docs" / "差异集清单.md"
EXPECTED_DIFFSET_PATHS = 120
EXPECTED_PATCH_FILES = {
    "diffset-02-package-integration.patch": 3,
    "diffset-07-desktop-test-expectations.patch": 24,
    "diffset-10-profile-backfill.patch": 1,
}
TOUCHED = [MODULE, MANAGER, SPEC]
UNPACKED_ASAR = (UPSTREAM / "apps" / "desktop" / ".desktop-build" / "targets" / "win-x64"
                 / "unsigned-artifacts" / "win-unpacked" / "resources" / "app.asar")
ASAR_MARKERS = (b"hub.example.com", b"enterprise-hub", b"ENTERPRISE_HUB_API_KEY")
# 产物里密钥扫描要用更严的判据：宽口径 `sk-[A-Za-z0-9_-]{8,}` 会把 CSS 的 `mask-*` 判成命中
# （实测 42 处全是 `mask-position` 这类片段），真实密钥是 40+ 位、且 `sk-` 前是词边界。
ASAR_SECRET = re.compile(r"\bsk-[A-Za-z0-9]{24,}\b")
PRODUCT_NAME = "WorkNexus-DSH"
INSTALL = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / PRODUCT_NAME

PROBE_SOURCE = """\
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { backfillProfileModelRoute, seededModelRoutePatch } from '../apps/desktop/src/profile-bundle-backfill.ts'

const TEMPLATE = '# Your patch layer for this dsh profile, applied after every bundle layer:\\n'
  + '# a top-level YAML array of loader patch entries (id-targeted config\\n'
  + '# overrides, disables, and insert lists; `!!js` expressions allowed).\\n'
  + '[]\\n'

function emit(probe, row) {
  console.log('RESULT ' + JSON.stringify({ probe, ...row }))
}

const SECRET = /sk-[A-Za-z0-9_-]{8,}/u
const ids = (text) => (text.match(/^- id: (\\S+)$/gmu) ?? []).map(line => line.slice(6))

// 官方模板：空列表必须被换成块序列（而不是在 `[]` 之后再写一个根节点）。
const seeded = seededModelRoutePatch(TEMPLATE)
emit('template', {
  seeded: seeded !== undefined,
  keepsHeader: seeded !== undefined && seeded.startsWith('# Your patch layer for this dsh profile'),
  noEmptyList: seeded !== undefined && !/\\[\\]/u.test(seeded),
  ids: seeded === undefined ? [] : ids(seeded),
  route: seeded !== undefined && seeded.includes('api: anthropic-messages')
    && seeded.includes('baseURL: https://hub.example.com')
    && seeded.includes('apiKeyEnv: ENTERPRISE_HUB_API_KEY')
    && seeded.includes('displayName: 企业方 Hub'),
  model: seeded !== undefined && seeded.includes('provider: enterprise-hub')
    && seeded.includes('model: deepseek-v4.1-flash'),
  idempotent: seeded !== undefined && seededModelRoutePatch(seeded) === undefined,
  secretFree: seeded !== undefined && !SECRET.test(seeded) && !seeded.includes('credentials.yaml'),
})

// 机器已有自己的默认模型（用户在选择器里切过 / 手改过）→ 整体让位，不写盘。
const OWN_SELECTION = '# own layer\\n- id: agent-default-model\\n'
  + "  name: '@deepseek-ai/dsh-agent-default-model'\\n  config:\\n"
  + '    provider: deepseek-official\\n    model: deepseek-flash\\n'
const OWN_ROUTE = '# own layer\\n- id: llm-pi-ai\\n  name: \\'@deepseek-ai/dsh-llm-pi-ai\\'\\n'
emit('withstands-own-selection', {
  selection: seededModelRoutePatch(OWN_SELECTION) === undefined,
  route: seededModelRoutePatch(OWN_ROUTE) === undefined,
})

// 已有块序列：只追加，既有字节逐字保留。
const USER_ENTRY = '# keep me\\n- id: better-sidebar\\n  disabled: true\\n'
const appended = seededModelRoutePatch(USER_ENTRY)
emit('append', {
  appended: appended !== undefined && appended.startsWith(USER_ENTRY),
  ids: appended === undefined ? [] : ids(appended),
  idempotent: appended !== undefined && seededModelRoutePatch(appended) === undefined,
})

// 我们不认识的形态（映射根）与只有注释的文件：前者拒绝写盘，后者等价空列表。
emit('refusals', {
  mapRoot: seededModelRoutePatch('a: 1\\n') === undefined,
  empty: seededModelRoutePatch('') !== undefined,
  commentsOnly: seededModelRoutePatch('# only a comment\\n') !== undefined,
})

// 真机路径：profile 目录里的用户层文件。
const root = mkdtempSync(join(tmpdir(), 't125-probe-'))
const fresh = join(root, 'fresh')
mkdirSync(fresh, { recursive: true })
writeFileSync(join(fresh, 'cordis.patch.yml'), TEMPLATE)
const firstWrite = backfillProfileModelRoute(fresh)
const afterFirst = readFileSync(join(fresh, 'cordis.patch.yml'), 'utf8')
const secondWrite = backfillProfileModelRoute(fresh)
const afterSecond = readFileSync(join(fresh, 'cordis.patch.yml'), 'utf8')
const missing = join(root, 'missing')
mkdirSync(missing, { recursive: true })
emit('backfill', {
  firstWrite,
  secondWrite,
  stable: afterFirst === afterSecond,
  seeded: afterFirst.includes('- id: llm-pi-ai') && afterFirst.includes('- id: agent-default-model'),
  missingReturnsFalse: backfillProfileModelRoute(missing) === false,
  missingNotCreated: !existsSync(join(missing, 'cordis.patch.yml')),
})
"""

RESULTS: list[tuple[bool, str]] = []


def record(ok: bool, detail: str) -> None:
    RESULTS.append((ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {detail}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def git(*args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.stdout


def patch_paths(patch_text: str) -> list[str]:
    return sorted({m.group(1) for m in re.finditer(r"^diff --git a/(.+?) b/", patch_text, re.MULTILINE)})


def changed_paths() -> list[str]:
    tracked = [line.strip() for line in git("diff", "--name-only", "HEAD").splitlines() if line.strip()]
    untracked = [line.strip() for line in git("ls-files", "--others", "--exclude-standard").splitlines()
                 if line.strip()]
    return sorted(set(tracked + untracked))


def run_probe() -> dict[str, dict[str, object]]:
    """在 fork 内的一次性目录里用真实 tsx 执行上游模块。"""
    tsx = UPSTREAM / "node_modules" / ".bin" / ("tsx.CMD" if sys.platform == "win32" else "tsx")
    if not tsx.exists():
        record(False, f"P2 探针前置缺失：找不到 {tsx}")
        return {}
    probe_dir = Path(tempfile.mkdtemp(prefix=".t125-probe-", dir=str(UPSTREAM)))
    try:
        (probe_dir / "probe.mts").write_text(PROBE_SOURCE, encoding="utf-8")
        proc = subprocess.run([str(tsx), str(probe_dir / "probe.mts")], cwd=str(UPSTREAM),
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            record(False, f"P2 探针执行失败：exit={proc.returncode} {(proc.stderr or proc.stdout).strip()[-400:]}")
            return {}
        results: dict[str, dict[str, object]] = {}
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT "):
                row = json.loads(line[len("RESULT "):])
                results[str(row.pop("probe"))] = row
        return results
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def launch_installed_client(dsh_home: Path) -> bool:
    """用隔离 `DSH_HOME` 与隔离 `--user-data-dir` 起一次安装态客户端（照 t112 A8/A11 口径）。"""
    executable = INSTALL / f"{PRODUCT_NAME}.exe"
    if not executable.exists():
        return False
    environment = dict(os.environ)
    environment["DSH_HOME"] = str(dsh_home)
    user_data = dsh_home / "user-data"
    user_data.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([str(executable), f"--user-data-dir={user_data}"], env=environment,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(35)
    try:
        process.terminate()
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001 - 收尾异常不改变判定
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    time.sleep(3)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="T-125 门禁")
    parser.add_argument("--launch", action="store_true",
                        help="追加装机态端到端探针（起一次安装态客户端、隔离 home）")
    options = parser.parse_args()

    print("=" * 60)
    print("T-125 门禁：发行版默认模型路由预置（差异集 02/07/10 扩项）")
    print("=" * 60)

    # ── P0 探活 ──
    record(UPSTREAM.is_dir(), f"P0 上游 fork 存在：{UPSTREAM}")
    record((UPSTREAM / MODULE).exists(), f"P0 上游模块存在：{MODULE}")
    record(bool(git("rev-parse", "--short", "HEAD").strip()),
           f"P0 上游 HEAD = {git('rev-parse', '--short', 'HEAD').strip()}")

    # ── P1 工作树 seam ──
    module = read(UPSTREAM / MODULE)
    manager = read(UPSTREAM / MANAGER)
    record("export function seededModelRoutePatch" in module
           and "export function backfillProfileModelRoute" in module,
           "P1 新模块导出 seededModelRoutePatch / backfillProfileModelRoute")
    record("export const WORKNEXUS_DEFAULT_MODEL_ENTRY_IDS" in module
           and "export const WORKNEXUS_DEFAULT_MODEL_ROUTE = 'enterprise-hub'" in module
           and "export const WORKNEXUS_DEFAULT_MODEL_BASE_URL = 'https://hub.example.com'" in module
           and "export const WORKNEXUS_DEFAULT_MODEL_API_KEY_REF = 'ENTERPRISE_HUB_API_KEY'" in module
           and "export const WORKNEXUS_DEFAULT_MODEL_ID = 'deepseek-v4.1-flash'" in module,
           "P1 预置常量齐备（路由名/模型 id/端点/凭据引用名/让位 id）")
    call = re.search(r"try \{\s*if \(backfillProfileModelRoute\(this\.paths\.profile\)\) \{", manager)
    record(call is not None and "applyRelease(): Promise<void>" in manager,
           "P1 applyRelease 内以 try/catch 调用补齐（写失败只告警、不阻断启动）")
    record("backfillProfileModelRoute" in manager.split("export function createPluginProfile")[0],
           "P1 调用点在启动路径（applyRelease），不在建 profile 路径")

    # ── P2 行为探针 ──
    probe = run_probe()
    if probe:
        template = probe.get("template", {})
        record(template.get("seeded") is True and template.get("keepsHeader") is True
               and template.get("noEmptyList") is True,
               "P2 官方模板 `[]` → 换成块序列且保留模板头（不再是空列表）")
        record(template.get("ids") == ["llm-pi-ai", "agent-default-model"],
               f"P2 预置两条行 id = {template.get('ids')}（期望 ['llm-pi-ai', 'agent-default-model']）")
        record(template.get("route") is True and template.get("model") is True,
               "P2 hub 路由（anthropic-messages + hub 端点 + 凭据引用名）与默认模型（enterprise-hub/deepseek-v4.1-flash）")
        record(template.get("idempotent") is True, "P2 幂等：对已补齐文本再跑不写盘")
        record(template.get("secretFree") is True, "P2 补齐产物无密钥字面量、不引用官方凭据文件")

        withstands = probe.get("withstands-own-selection", {})
        record(withstands.get("selection") is True and withstands.get("route") is True,
               "P2 机器已有 agent-default-model 或 llm-pi-ai 任一自有行 → 整体让位")

        append = probe.get("append", {})
        record(append.get("appended") is True
               and append.get("ids") == ["better-sidebar", "llm-pi-ai", "agent-default-model"],
               "P2 追加不改既有字节（用户层前缀逐字保留）")
        record(append.get("idempotent") is True, "P2 追加后再跑不写盘")

        refusals = probe.get("refusals", {})
        record(refusals.get("mapRoot") is True, "P2 映射根等不认识的形态 → 拒绝写盘")
        record(refusals.get("empty") is True and refusals.get("commentsOnly") is True,
               "P2 空文件与只有注释的文件 → 视为空列表补齐")

        backfill = probe.get("backfill", {})
        record(backfill.get("firstWrite") is True and backfill.get("seeded") is True,
               "P2 profile 用户层真实写盘一次（两条行落盘）")
        record(backfill.get("secondWrite") is False and backfill.get("stable") is True,
               "P2 第二次启动不写盘且字节不变")
        record(backfill.get("missingReturnsFalse") is True and backfill.get("missingNotCreated") is True,
               "P2 用户层缺失 → 不写盘也不抛错（交由官方加载链路）")

    # ── P3 无密钥 ──
    secret = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
    record(not secret.search(module), "P3 模块内无密钥字面量")
    record("credentials.yaml" not in module and "credentials" not in module,
           "P3 模块不触碰官方凭据存储（只写引用名）")
    patch_hits = [str(path.name) for path in sorted(PATCHES.glob("diffset-*.patch"))
                  if secret.search(path.read_text(encoding="utf-8", errors="replace"))]
    record(not patch_hits, f"P3 差异集补丁无密钥字面量（命中：{patch_hits or '无'}）")

    # ── P4 差异集口径 ──
    for name, expected in EXPECTED_PATCH_FILES.items():
        paths = patch_paths(read(PATCHES / name))
        record(len(paths) == expected, f"P4 {name} 枚举 = {len(paths)} 文件（期望 {expected}）")
    paths = changed_paths()
    record(len(paths) == EXPECTED_DIFFSET_PATHS,
           f"P4 上游差异集条目数 = {len(paths)}（期望 {EXPECTED_DIFFSET_PATHS}：本次不新增条目）")
    enumerated: set[str] = set()
    for patch in sorted(PATCHES.glob("diffset-*.patch")):
        enumerated.update(patch_paths(patch.read_text(encoding="utf-8", errors="replace")))
    record(all(path in enumerated for path in TOUCHED),
           f"P4 本次改动的 {len(TOUCHED)} 个文件都在既有差异集枚举内（不新增条目）")

    # ── P5 上游 spec 只就地改期望 ──
    spec_diff = git("diff", "HEAD", "--", SPEC)
    declarations = [line for line in spec_diff.splitlines()
                    if re.match(r"^[+-]\s*(describe|it)\(", line)]
    record(not declarations,
           f"P5 {SPEC} 用例声明增删 = {len(declarations)}（期望 0：只就地更新期望值）")

    # ── P6 文档齐备 ──
    delivery = read(DELIVERY_DOC)
    sections = ["## 1. 结论先行", "## 2. 改动清单", "## 3. 验证证据表", "## 4. 未验证项与边界",
                "## 5. 复现命令", "## 6. 下一步"]
    record(bool(delivery) and all(section in delivery for section in sections),
           "P6 交付说明存在且六段齐备（docs/发行版默认模型路由_T-125.md）")
    record("T-125" in read(INDEX), "P6 开发文档索引已登记 T-125")
    record("T-125" in read(DIFFSET_REGISTRY), "P6 差异集清单已登记 T-125 扩项")
    record("T-125" in read(LEDGER), "P6 当日账本已回写 T-125")

    # ── P7 负向 ──
    boot = [line for line in git("diff", "--name-only", "HEAD", "--", "packages/boot").splitlines() if line.strip()]
    record(not boot, f"P7 packages/boot/** 未被改动（N-3 加载顺序不动；命中：{boot or '无'}）")

    # ── P8 产物标记（出包后才有；未出包时跳过而非判红）──
    if UNPACKED_ASAR.exists():
        data = UNPACKED_ASAR.read_bytes()
        counts = {marker.decode(): data.count(marker) for marker in ASAR_MARKERS}
        record(all(count > 0 for count in counts.values()),
               f"P8 产物 app.asar 含默认路由标记（{counts}）")
        asar_text = data.decode("utf-8", "replace")
        asar_hits = ASAR_SECRET.findall(asar_text)
        record(not asar_hits,
               f"P8 产物 app.asar 内无密钥值（严口径命中：{len(asar_hits)}）")
    else:
        record(True, f"P8 跳过：未出包（{UNPACKED_ASAR.relative_to(REPO)} 不存在）")

    # ── P9 装机态端到端（新机路径）──
    if options.launch:
        if not (INSTALL / f"{PRODUCT_NAME}.exe").exists():
            record(False, f"P9 装机前置缺失：找不到 {INSTALL / f'{PRODUCT_NAME}.exe'}")
        else:
            home = Path(tempfile.mkdtemp(prefix=".t125-launch-", dir=str(REPO / ".dsh-check")))
            try:
                launched = launch_installed_client(home)
                patch = home / "profiles" / "desktop" / "cordis.patch.yml"
                manifest = home / "profiles" / "desktop" / "package.json"
                text = read(patch)
                record(launched and patch.exists(), f"P9 隔离 home 起壳后生成用户层（{patch.name}）")
                record("- id: llm-pi-ai" in text and "- id: agent-default-model" in text,
                       "P9 新 profile 用户层被自动补上默认路由两条行")
                record("https://hub.example.com" in text and "ENTERPRISE_HUB_API_KEY" in text
                       and "deepseek-v4.1-flash" in text,
                       "P9 补入内容指向 hub 与 deepseek-v4.1-flash（密钥仅引用名）")
                record(not ASAR_SECRET.search(text), "P9 用户层不含密钥值")
                try:
                    bundles = (json.loads(read(manifest)).get("dsh") or {}).get("profile", {}).get("bundles") or []
                except Exception:  # noqa: BLE001 - manifest 不可读按失败处理
                    bundles = []
                record("@worknexus/ent-core" in bundles,
                       f"P9 profile manifest 含企业 bundle（共 {len(bundles)} 条）")
            finally:
                shutil.rmtree(home, ignore_errors=True)

    failures = [detail for ok, detail in RESULTS if not ok]
    print("-" * 60)
    print(f"结果: {len(RESULTS) - len(failures)} [OK] / {len(failures)} [FAIL]")
    if failures:
        for detail in failures:
            print(f"  [FAIL] {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
