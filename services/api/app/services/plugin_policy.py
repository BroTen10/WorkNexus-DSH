"""插件兼容性与版本锁定策略（T-103，需求书 P6B-F04/F05、§5.5）。

规则：
  - 插件必须声明 `dshCompatibility`（DSH 版本范围）与 `hostCoreCompatibility`（Host Core 契约版本范围）；
  - 比较按 semver（含 prerelease 排序）：`0.2.0-rc.1 < 0.2.0`；契约版本独立于产品版本演进（§2.1 第 17 条）；
  - 版本锁定：锁定后不允许自动升级（升级请求返回 409），需要管理员先解锁或显式改白名单版本。

本模块只做纯函数判定，不访问数据库；端点负责读写实体。
"""

from __future__ import annotations

import re
from typing import Iterable

# 与 packages/contracts/src/version.ts 的 HOST_CORE_CONTRACT_VERSION 保持同源（门禁会校验一致）
CONTRACT_VERSION = "1.1.0"
# 与 docs/技术决策-版本锁定.md 的锁定 tag 保持同源
DSH_PINNED_VERSION = "0.2.0-rc.1"

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")
_COMPARATOR_RE = re.compile(r"^(>=|<=|>|<|=|\^|~)?\s*(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)$")


def parse_version(value: str) -> tuple[int, int, int, str | None] | None:
    match = _VERSION_RE.match(value.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4)


def _compare_prerelease(left: str, right: str) -> int:
    left_parts = left.split(".")
    right_parts = right.split(".")
    for index in range(max(len(left_parts), len(right_parts))):
        if index >= len(left_parts):
            return -1
        if index >= len(right_parts):
            return 1
        a, b = left_parts[index], right_parts[index]
        a_num, b_num = a.isdigit(), b.isdigit()
        if a_num and b_num:
            if int(a) != int(b):
                return -1 if int(a) < int(b) else 1
        elif a_num != b_num:
            return -1 if a_num else 1
        elif a != b:
            return -1 if a < b else 1
    return 0


def compare_versions(left: str, right: str) -> int:
    """返回 -1 / 0 / 1；非法版本抛 ValueError。"""
    parsed_left = parse_version(left)
    parsed_right = parse_version(right)
    if parsed_left is None or parsed_right is None:
        raise ValueError(f"invalid semver: {left!r} / {right!r}")
    core_left, pre_left = parsed_left[:3], parsed_left[3]
    core_right, pre_right = parsed_right[:3], parsed_right[3]
    if core_left != core_right:
        return -1 if core_left < core_right else 1
    if pre_left is None and pre_right is None:
        return 0
    if pre_left is None:
        return 1
    if pre_right is None:
        return -1
    return _compare_prerelease(pre_left, pre_right)


def validate_range(value: str) -> list[str]:
    """校验 semver 范围写法；返回问题列表（空表示合法）。"""
    text = (value or "").strip()
    if not text:
        return ["范围不能为空"]
    for token in re.split(r"[,，\s]+", text):
        if not token:
            continue
        if _COMPARATOR_RE.match(token) is None:
            return [f"非法比较项: {token}"]
    return []


def _satisfies_token(version: str, token: str) -> bool:
    match = _COMPARATOR_RE.match(token)
    if match is None:
        return False
    operator = match.group(1) or "="
    target = match.group(2)
    if operator in ("^", "~"):
        order = compare_versions(version, target)
        if order < 0:
            return False
        version_core = parse_version(version)
        target_core = parse_version(target)
        assert version_core is not None and target_core is not None
        if operator == "^":
            return version_core[0] == target_core[0]
        return version_core[0] == target_core[0] and version_core[1] == target_core[1]
    order = compare_versions(version, target)
    return {
        ">=": order >= 0,
        "<=": order <= 0,
        ">": order > 0,
        "<": order < 0,
        "=": order == 0,
    }[operator]


def version_in_range(version: str, range_text: str) -> bool:
    tokens = [token for token in re.split(r"[,，\s]+", (range_text or "").strip()) if token]
    if not tokens:
        return False
    if parse_version(version) is None:
        return False
    return all(_satisfies_token(version, token) for token in tokens)


def validate_declaration(dsh_compatibility: str | None, host_core_compatibility: str | None) -> list[str]:
    problems: list[str] = []
    if not dsh_compatibility or not dsh_compatibility.strip():
        problems.append("dshCompatibility: 必填（DSH 版本范围，见 §5.5 第 2 条）")
    else:
        problems.extend(f"dshCompatibility: {item}" for item in validate_range(dsh_compatibility))
    if not host_core_compatibility or not host_core_compatibility.strip():
        problems.append("hostCoreCompatibility: 必填（Host Core 契约版本范围）")
    else:
        problems.extend(f"hostCoreCompatibility: {item}" for item in validate_range(host_core_compatibility))
    return problems


def check_compatibility(
    *,
    dsh_compatibility: str | None,
    host_core_compatibility: str | None,
    dsh_version: str = DSH_PINNED_VERSION,
    contract_version: str = CONTRACT_VERSION,
) -> dict[str, object]:
    problems = validate_declaration(dsh_compatibility, host_core_compatibility)
    if problems:
        return {"ok": False, "problems": problems}
    if not version_in_range(dsh_version, dsh_compatibility or ""):
        problems.append(
            f"dshCompatibility: DSH {dsh_version} 不在声明范围 {dsh_compatibility} 内"
        )
    if not version_in_range(contract_version, host_core_compatibility or ""):
        problems.append(
            f"hostCoreCompatibility: 契约 {contract_version} 不在声明范围 {host_core_compatibility} 内"
        )
    return {"ok": not problems, "problems": problems}


def upgrade_allowed(*, locked: bool, target_version: str, locked_version: str | None) -> dict[str, object]:
    """锁定后禁止自动升级（P6B-F04）。"""
    if locked:
        return {
            "allowed": False,
            "reason": "version_locked",
            "detail": f"插件版本已锁定为 {locked_version or '当前版本'}，升级需管理员显式解除锁定",
        }
    return {"allowed": True, "reason": "ok", "targetVersion": target_version}


def summarize(problems: Iterable[str]) -> str:
    return "；".join(problems)
