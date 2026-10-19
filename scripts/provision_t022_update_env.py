#!/usr/bin/env python
"""T-022 辅助：把企业更新源/签名模板落到上游 fork 的本地 `.env.windows`。

为什么需要它：企业与签名的真实值**不得入库**（T-000 D-1、T-007 §6 第 4 条）。因此
模板入库（`configs/desktop/enterprise-update.env.example`），真实值只写进被上游
`.gitignore` 忽略的 `repos/deepseek-harness/apps/desktop/.env.windows`。

用法：
  # 只检查（默认）：模板完整性、占位未被替换、目标落点被忽略且未被跟踪
  python scripts/provision_t022_update_env.py --check

  # 生成/更新本地 .env.windows（值全部来自 --set，未给出的沿用模板）
  python scripts/provision_t022_update_env.py --write \
      --set DOWNLOAD_TEST_ORIGIN=https://updates.corp.example \
      --set DOWNLOAD_TEST_RELEASE_ID=0123456789abcdef0123456789abcdef

退出码：0 = 通过；1 = 任一项 [FAIL]。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "configs" / "desktop" / "enterprise-update.env.example"
UPSTREAM = REPO / "repos" / "deepseek-harness"
TARGET = UPSTREAM / "apps" / "desktop" / ".env.windows"

REQUIRED_KEYS = [
    "DSH_DESKTOP_APP_ID",
    "DSH_DESKTOP_AUTO_UPDATE_ENV",
    "DOWNLOAD_TEST_ORIGIN",
    "DOWNLOAD_TEST_RELEASE_ID",
    "DSH_DESKTOP_MANDATORY_UPDATE_TEST_ORIGIN",
    "DSH_DESKTOP_MANDATORY_UPDATE_PROD_ORIGIN",
    "DSH_DESKTOP_MANDATORY_UPDATE_CONFIG",
    "DSH_DESKTOP_WINDOWS_CER_FILE",
    "DSH_DESKTOP_WINDOWS_SIGNTOOL",
    "DSH_DESKTOP_WINDOWS_KEY_CONTAINER",
    "DSH_DESKTOP_WINDOWS_TOKEN_PIN",
]

# 本地可自足、写入后必须非空的键（凭据类与 production origin 属外部输入，允许留空）
LOCAL_REQUIRED_KEYS = [
    "DSH_DESKTOP_APP_ID",
    "DSH_DESKTOP_AUTO_UPDATE_ENV",
    "DOWNLOAD_TEST_ORIGIN",
    "DOWNLOAD_TEST_RELEASE_ID",
    "DSH_DESKTOP_MANDATORY_UPDATE_TEST_ORIGIN",
    "DSH_DESKTOP_MANDATORY_UPDATE_CONFIG",
]

# 必须由外部输入（证书 / 正式域名）填充的键；留空即登记为待人工项
EXTERNAL_KEYS = [
    "DSH_DESKTOP_MANDATORY_UPDATE_PROD_ORIGIN",
    "DSH_DESKTOP_WINDOWS_CER_FILE",
    "DSH_DESKTOP_WINDOWS_SIGNTOOL",
    "DSH_DESKTOP_WINDOWS_KEY_CONTAINER",
    "DSH_DESKTOP_WINDOWS_TOKEN_PIN",
]

# 模板里必须留空、绝不写值的键（凭据类）
SECRET_KEYS = [
    "DSH_DESKTOP_WINDOWS_CER_FILE",
    "DSH_DESKTOP_WINDOWS_SIGNTOOL",
    "DSH_DESKTOP_WINDOWS_KEY_CONTAINER",
    "DSH_DESKTOP_WINDOWS_TOKEN_PIN",
    "DOWNLOAD_TEST_COS_SECRET_ID",
    "DOWNLOAD_TEST_COS_SECRET_KEY",
    "DOWNLOAD_PROD_COS_SECRET_ID",
    "DOWNLOAD_PROD_COS_SECRET_KEY",
]

HTTPS_ORIGIN = re.compile(r"^https://[A-Za-z0-9.\-]+(?::\d+)?$")
RELEASE_ID = re.compile(r"^[a-f0-9]{32}$")
PLACEHOLDER = ".invalid"

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


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip()
    return values


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(UPSTREAM), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def check() -> int:
    if not TEMPLATE.exists():
        record(False, f"模板存在: {TEMPLATE}")
        return finish()
    record(True, f"模板存在: {TEMPLATE.relative_to(REPO)}")

    template_text = TEMPLATE.read_text(encoding="utf-8")
    values = parse_env(template_text)
    missing = [k for k in REQUIRED_KEYS if k not in values]
    record(not missing, f"模板含全部必需键（缺: {missing or '无'}）")

    filled = [k for k in SECRET_KEYS if values.get(k, "") != ""]
    record(not filled, f"模板中凭据类键一律留空（非空: {filled or '无'}）")

    # origin 必须是 https origin；release id 必须是 32 位小写 hex
    origin = values.get("DOWNLOAD_TEST_ORIGIN", "")
    record(bool(HTTPS_ORIGIN.match(origin)), f"DOWNLOAD_TEST_ORIGIN 为合法 HTTPS origin: {origin}")
    release_id = values.get("DOWNLOAD_TEST_RELEASE_ID", "")
    record(bool(RELEASE_ID.match(release_id)), f"DOWNLOAD_TEST_RELEASE_ID 为 32 位小写十六进制: {release_id}")
    record(PLACEHOLDER in origin, "模板仍是占位值（.invalid），未被真实企业域名替换")

    # 目标落点必须被上游忽略，且未被 git 跟踪
    ignored = git("check-ignore", "-q", "apps/desktop/.env.windows")
    record(ignored.returncode == 0, "apps/desktop/.env.windows 被上游 .gitignore 忽略")
    tracked = git("ls-files", "--error-unmatch", "apps/desktop/.env.windows")
    record(tracked.returncode != 0, "apps/desktop/.env.windows 未被 git 跟踪")

    if TARGET.exists():
        local = parse_env(TARGET.read_text(encoding="utf-8"))
        record(True, f"本地 .env.windows 已存在（{len(local)} 个键）")
    else:
        record(True, "本地 .env.windows 尚未生成（--write 时创建）")

    # 我方仓库里不得出现任何 .env.windows 实体（跳过 repos/ 与 node_modules/，避免扫描上游树）
    stray: list[str] = []
    for current, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in {"repos", "node_modules", ".git", ".dsh-check"}]
        for name in files:
            if name == ".env.windows":
                stray.append(Path(current, name).relative_to(REPO).as_posix())
    record(not stray, f"我方仓库内无 .env.windows 实体（发现: {stray or '无'}）")
    return finish()


def write(overrides: dict[str, str]) -> int:
    if not TEMPLATE.exists():
        record(False, f"模板存在: {TEMPLATE}")
        return finish()
    values = parse_env(TEMPLATE.read_text(encoding="utf-8"))
    unknown = [k for k in overrides if k not in values]
    record(not unknown, f"--set 的键都在模板内（未知: {unknown or '无'}）")
    if unknown:
        return finish()

    if "DOWNLOAD_TEST_ORIGIN" in overrides and not HTTPS_ORIGIN.match(overrides["DOWNLOAD_TEST_ORIGIN"]):
        record(False, "DOWNLOAD_TEST_ORIGIN 必须是形如 https://host[:port] 的 origin（无路径/凭据/查询/片段）")
        return finish()
    if "DOWNLOAD_TEST_RELEASE_ID" in overrides and not RELEASE_ID.match(overrides["DOWNLOAD_TEST_RELEASE_ID"]):
        record(False, "DOWNLOAD_TEST_RELEASE_ID 必须是 32 位小写十六进制")
        return finish()

    ignored = git("check-ignore", "-q", "apps/desktop/.env.windows")
    if ignored.returncode != 0:
        record(False, "目标未被忽略，拒绝写入（避免把真实配置提交进上游）")
        return finish()
    record(True, "目标被忽略，可安全写入")

    lines = []
    for raw in TEMPLATE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        name = stripped.partition("=")[0].strip() if "=" in stripped and not stripped.startswith("#") else ""
        if name and name in overrides:
            lines.append(f"{name}={overrides[name]}")
        else:
            lines.append(raw)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record(True, f"已写入本地配置: {TARGET}")
    written = parse_env(TARGET.read_text(encoding="utf-8"))
    remaining = [k for k in LOCAL_REQUIRED_KEYS if written.get(k, "") == ""]
    record(not remaining, f"本地可自足键均已填充（空: {remaining or '无'}）")
    pending = [k for k in EXTERNAL_KEYS if written.get(k, "") == ""]
    print(f"[INFO] 待外部输入的键（不计 FAIL）: {pending or '无'}")
    print("提示：本文件不在版本控制内，请勿粘贴到文档、提交或聊天中。")
    return finish()


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="只做落点与模板检查（默认）")
    group.add_argument("--write", action="store_true", help="生成/更新本地 .env.windows")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    args = ap.parse_args()

    overrides: dict[str, str] = {}
    for item in args.set:
        name, sep, value = item.partition("=")
        if not sep:
            print(f"[FAIL] --set 需要 KEY=VALUE 形式: {item}")
            return 1
        overrides[name.strip()] = value.strip()

    if args.write:
        return write(overrides)
    if overrides:
        print("[FAIL] --set 只能与 --write 一起使用")
        return 1
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
