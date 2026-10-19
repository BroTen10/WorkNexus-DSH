#!/usr/bin/env python
"""生成「WorkNexus-DSH 发行版第三方组件声明」（差异集 14）。

为什么需要本文件（而不是改上游 `THIRD_PARTY_NOTICES.md`）：

1. 上游 `THIRD_PARTY_NOTICES.md` 由 `scripts/gen-third-party-notices.ts` **生成**，
   文件头写明 *do not edit by hand*，且 `gen-third-party-notices.spec.ts` 断言提交字节与生成结果一致
   —— 手工追加会被门禁与上游 spec 同时否掉。
2. 上游生成器只扫描**上游 pnpm workspace 的 `package.json`**；而本发行版的企业层与第三方预置包
   是**以 tgz 分层随包**的，不在上游 workspace 里，因此不会出现在那份文件里
   （实测：`THIRD_PARTY_NOTICES.md` 不含 `dshmarket`，也不含任何 `@worknexus/*`）。

因此这里产出**发行版附加声明**，与上游文件并存、互不替代，由差异集 02 的 electron-builder 配置
一并落到安装目录（与 `WORKNEXUS-RELEASE-NOTES.md` 同一处置）。内容全部来自可复核的输入：
`configs/vendor/third-party-bundles.lock.json` 与 `configs/vendor/licenses/*`（取自上游 tarball 原文）。

用法：
  python scripts/gen_worknexus_notices.py            # 写入上游检出根目录
  python scripts/gen_worknexus_notices.py --check    # 只校验（字节不一致退出码 1）
  python scripts/gen_worknexus_notices.py --stdout    # 打印到标准输出

退出码：成功 0；`--check` 不一致或输入缺失 1。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "configs" / "vendor" / "third-party-bundles.lock.json"
LICENSES = REPO / "configs" / "vendor" / "licenses"
UPSTREAM = REPO / "repos" / "deepseek-harness"
TARGET = UPSTREAM / "WORKNEXUS-THIRD-PARTY-NOTICES.md"

HEADER = """\
<!-- 由 scripts/gen_worknexus_notices.py 生成 —— 请勿手工编辑。
     重新生成：python scripts/gen_worknexus_notices.py
     校验：python scripts/verify_diffset14_third_party_notices.py -->

# WorkNexus-DSH 发行版第三方组件声明

本文件是**发行版附加声明**，与上游生成的 `THIRD_PARTY_NOTICES.md` 并存、互不替代。
上游生成器只扫描上游 pnpm workspace 的 `package.json`，因此**以 tgz 分层随发行版预置**的组件
不在其中；本文件补齐这部分（合规依据：需求书 P1-F17 与 §4.1.5 第 9 条）。

## 1. 随发行版预置的第三方组件

| 组件 | 版本 | 许可证 | 上游来源 | 在本发行版中的角色 |
| --- | --- | --- | --- | --- |
"""

FOOTER = """
## 3. 许可证原文
"""

OWN_SECTION = """\
## 2. 我方自研组件

本仓为 WorkNexus-DSH 个人版宿主仓，不承载 `@worknexus/*` 自研包；企业层组件在
`WorkNexus-Enterprise` 单独登记，不随本发行版分发。
"""


def license_stem(name: str, version: str) -> str:
    """许可证原文的落盘名（scoped 包的 `/` 换成 `-`，与取回脚本一致）。"""
    return f"{name.replace('/', '-')}-{version}"


def render() -> str:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    packages = sorted(lock["packages"], key=lambda entry: (entry["name"], entry["version"]))
    parts: list[str] = [HEADER]
    for entry in packages:
        role = {
            "bundle-root": "插件市场 UI（`dsh-market` 行由 `@worknexus/plugin-market` 挂载）",
            "runtime-dependency": "随包预置插件的声明依赖（版本钉死随包，保证离线安装与可复现；客户端半边已自带打包）",
        }.get(entry.get("role", ""), entry.get("role", ""))
        # 逐条可覆盖：预置插件各自说明它在发行版里的作用（同一角色下语义不同）。
        role = entry.get("roleLabel") or role
        parts.append(
            f"| `{entry['name']}` | {entry['version']} | {entry['license']} | {entry['url']} | {role} |\n"
        )
    parts.append("\n")
    parts.append(OWN_SECTION)
    parts.append(FOOTER)
    for entry in packages:
        license_file = LICENSES / f"{license_stem(entry['name'], entry['version'])}.LICENSE.txt"
        if not license_file.is_file():
            raise SystemExit(f"gen_worknexus_notices: 缺少许可证原文 {license_file.relative_to(REPO)}")
        text = license_file.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
        parts.append(f"\n### `{entry['name']}` {entry['version']}（{entry['license']}）\n\n```\n{text}\n```\n")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验上游文件与生成结果是否逐字节一致")
    parser.add_argument("--stdout", action="store_true", help="打印到标准输出，不写文件")
    args = parser.parse_args()

    content = render()
    if args.stdout:
        print(content, end="")
        return 0
    if args.check:
        if not TARGET.is_file():
            print(f"[FAIL] 缺少 {TARGET.relative_to(REPO)}")
            return 1
        actual = TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
        if actual != content:
            print("[FAIL] 声明文件与生成结果不一致（请重跑 python scripts/gen_worknexus_notices.py）")
            return 1
        print(f"[OK] {TARGET.relative_to(REPO)} 与生成结果逐字节一致（{len(content.encode('utf-8'))} 字节）")
        return 0
    TARGET.write_text(content, encoding="utf-8", newline="\n")
    print(f"[OK] 已写入 {TARGET.relative_to(REPO)}（{len(content.encode('utf-8'))} 字节）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
