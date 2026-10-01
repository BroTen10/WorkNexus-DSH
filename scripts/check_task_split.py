#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WorkNexus-DSH 任务拆分门禁（v3.0）。

用途：机器校验「需求说明书 v1.2 → v3.0 任务拆分」的一致性，替代人工通读。

检查项：
  C1  需求条目覆盖：需求说明书 v1.2 中出现的每个功能条目编号（P<n>[A-Z]?-F<nn>）
      都必须在**派发卡**中找到归属（总览的覆盖矩阵只作交叉核对，不能单独满足本项）；
      支持 `P1-F02~F04`、`P4-F01/F02` 这类紧凑写法展开。
  C2  章节约束锚点：v1.2 的关键章节（§3.2 ~ §13.3）必须被计划文档引用。
  C3  任务编号唯一且总数为 75，新增任务（T-000/T-029/T-035/T-054/T-106/T-107/T-108）必须存在。
  C4  依赖可达：每个任务的「依赖」必须指向存在的任务编号，且依赖图无环。
  C5  派发卡必备块：每张卡片必须含 输入 / 产出 / 步骤 / 验证 / DoD / 禁止 / 裁决 / 报告。
  C6  卡片的「元信息」行必须含 批次 / 依赖 / 并行组 / 无人值守 四个字段。
  C7  附录引用有效：卡片声明的「附录 X §T-nnn」必须在对应附录文件中存在该任务小节。
  C8  版本与口径：不得残留「八条验收」「需求说明书 v1.1」「尚未处理」等陈旧表述；
      §4.1.5 必须写「十条」、§4.2.7 必须写「九条」。

用法：
  python scripts/check_task_split.py --root . --stats

退出码：全部通过为 0；存在 [FAIL] 为 1。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台默认 GBK，门禁输出固定 UTF-8
    sys.stdout.reconfigure(encoding="utf-8")

CARD_FILE = "docs/任务卡-WorkNexus-DSH_v3.0_派发卡.md"
OVERVIEW_FILE = "docs/任务拆分-WorkNexus-DSH_总览与任务索引_v3.0_T-000~T-105.md"
SPEC_FILE = "docs/WorkNexus-DSH-需求说明书-v1.2.md"
REPORT_FILE = "docs/任务拆分检查报告-WorkNexus-DSH_v1.2.md"
APPENDICES = {
    "A": "docs/附录A-步骤明细-P0上游对齐与P1企业发行版_T-001~T-028.md",
    "B": "docs/附录B-步骤明细-HostCore与P2企业管理_T-030~T-053.md",
    "C": "docs/附录C-步骤明细-P3-P6业务插件_T-060~T-105.md",
}

REQUIRED_BLOCKS = ["输入", "产出", "步骤", "验证", "DoD", "禁止", "裁决", "报告"]
META_FIELDS = ["依赖", "并行组", "无人值守"]
NEW_TASKS = ["T-000", "T-029", "T-035", "T-054", "T-106", "T-107", "T-108"]
EXPECTED_TASK_COUNT = 75

CHAPTER_ANCHORS = [
    "§3.2", "§3.3", "§3.4", "§3.5",
    "§4.1.4", "§4.1.5", "§4.2.4", "§4.2.6", "§4.2.7",
    "§4.3.4", "§4.4.4", "§4.5.4", "§4.6.1", "§4.6.2",
    "§5.2", "§5.3", "§5.4", "§5.5", "§6.1", "§6.3", "§6.4",
    "§7.1", "§11", "§13.3",
]

STALE_PATTERNS = ["八条验收", "需求说明书 v1.1", "尚未处理"]

RESULTS: list[tuple[bool, str, str]] = []


def record(ok: bool, code: str, detail: str) -> None:
    RESULTS.append((ok, code, detail))


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_cards(text: str) -> dict[str, dict]:
    cards: dict[str, dict] = {}
    current: dict | None = None
    for line in text.splitlines():
        m = re.match(r"^###\s+(T-\d{3})\s+(.*)$", line)
        if m:
            current = {
                "id": m.group(1),
                "name": m.group(2).replace("*", "").strip(),
                "lines": [],
            }
            cards[current["id"]] = current
            continue
        if current is not None:
            current["lines"].append(line)
    for card in cards.values():
        card["body"] = "\n".join(card["lines"])
        card["meta"] = next(
            (l for l in card["lines"] if l.strip().startswith("- **元信息**")), ""
        )
        card["deps"] = _parse_deps(card["meta"])
        card["unattended"] = _parse_field(card["meta"], "无人值守")
        card["group"] = _parse_field(card["meta"], "并行组")
        card["batch"] = card["meta"].split("｜")[0].replace("- **元信息**：", "").strip() if card["meta"] else ""
        card["delta"] = _parse_field(card["meta"], "增补自")
    return cards


def _parse_field(meta: str, name: str) -> str:
    for part in meta.split("｜"):
        part = part.strip()
        if part.startswith(name):
            return part[len(name):].strip(" ：:")
    return ""


def _parse_deps(meta: str) -> list[str]:
    raw = _parse_field(meta, "依赖")
    if not raw or raw in {"无", "—", "-"}:
        return []
    return [d for d in re.split(r"[,，、\s]+", raw) if re.match(r"^T-\d{3}$", d)]


def expand_requirement_ids(text: str) -> set[str]:
    """收集需求条目编号，并展开紧凑写法（P1-F02~F04、P4-F01/F02、P6B-F02/F03）。"""
    ids = set(re.findall(r"P\d[A-Z]?-F\d{2}", text))
    for m in re.finditer(r"(P\d[A-Z]?-)(?:F)?(\d{2})\s*[~～]\s*(?:F)?(\d{2})", text):
        pre, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        for n in range(min(a, b), max(a, b) + 1):
            ids.add(f"{pre}F{n:02d}")
    for m in re.finditer(r"(P\d[A-Z]?-)(F\d{2})((?:[/、,，]\s*(?:F)?\d{2})+)", text):
        pre, first, rest = m.group(1), m.group(2), m.group(3)
        for suffix in [first] + re.findall(r"(?:F)?(\d{2})", rest):
            ids.add(f"{pre}F{int(suffix.lstrip('F')):02d}")
    return ids


def check_requirement_coverage(spec: str, cards_text: str, overview: str) -> None:
    spec_ids = sorted(set(re.findall(r"P\d[A-Z]?-F\d{2}", spec)))
    card_ids = expand_requirement_ids(cards_text)
    overview_ids = expand_requirement_ids(overview)
    missing_cards = [rid for rid in spec_ids if rid not in card_ids]
    missing_overview = [rid for rid in spec_ids if rid not in overview_ids]
    detail = (
        f"需求条目覆盖（派发卡 {len(spec_ids) - len(missing_cards)}/{len(spec_ids)}"
        f"，总览交叉核对 {len(spec_ids) - len(missing_overview)}/{len(spec_ids)}）"
    )
    if missing_cards:
        detail += f"；派发卡缺失：{', '.join(missing_cards)}"
    if missing_overview:
        detail += f"；总览缺失：{', '.join(missing_overview)}"
    record(not missing_cards and not missing_overview, "C1", detail)


def check_chapter_anchors(corpus: str) -> None:
    missing = [a for a in CHAPTER_ANCHORS if a not in corpus]
    record(
        not missing,
        "C2",
        f"章节约束锚点 {len(CHAPTER_ANCHORS) - len(missing)}/{len(CHAPTER_ANCHORS)}"
        + (f"（缺失：{', '.join(missing)}）" if missing else ""),
    )


def check_task_ids(cards: dict[str, dict]) -> None:
    ok = len(cards) == EXPECTED_TASK_COUNT
    detail = f"任务卡片 {len(cards)} 张（期望 {EXPECTED_TASK_COUNT}）"
    missing_new = [t for t in NEW_TASKS if t not in cards]
    if missing_new:
        ok = False
        detail += f"；缺新增任务 {', '.join(missing_new)}"
    record(ok, "C3", detail)


def check_dependencies(cards: dict[str, dict]) -> None:
    known = set(cards)
    dangling: dict[str, list[str]] = {}
    for tid, card in cards.items():
        bad = [d for d in card["deps"] if d not in known]
        if bad:
            dangling[tid] = bad

    # cycle detection
    WHITE, GREY, BLACK = 0, 1, 2
    color = {t: WHITE for t in known}
    cycles: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        color[node] = GREY
        for dep in cards[node]["deps"]:
            if dep not in known:
                continue
            if color[dep] == GREY:
                cycles.append(" -> ".join(stack + [node, dep]))
            elif color[dep] == WHITE:
                visit(dep, stack + [node])
        color[node] = BLACK

    for t in known:
        if color[t] == WHITE:
            visit(t, [])

    ok = not dangling and not cycles
    detail = "依赖可达且无环"
    if dangling:
        detail = "悬空依赖：" + "; ".join(f"{k}->{v}" for k, v in list(dangling.items())[:5])
    if cycles:
        detail += "；检测到环：" + "; ".join(cycles[:3])
    record(ok, "C4", detail)


def check_required_blocks(cards: dict[str, dict]) -> None:
    bad: list[str] = []
    for tid, card in cards.items():
        missing = [b for b in REQUIRED_BLOCKS if f"- **{b}**" not in card["body"]]
        if missing:
            bad.append(f"{tid}(缺 {','.join(missing)})")
    record(not bad, "C5", "派发卡必备块齐备" if not bad else "缺块：" + "; ".join(bad[:6]))


def check_meta_fields(cards: dict[str, dict]) -> None:
    bad: list[str] = []
    for tid, card in cards.items():
        if not card["meta"]:
            bad.append(f"{tid}(无元信息行)")
            continue
        if not card["batch"]:
            bad.append(f"{tid}(缺批次)")
        missing = [f for f in META_FIELDS if not _parse_field(card["meta"], f)]
        if missing:
            bad.append(f"{tid}(缺 {','.join(missing)})")
    record(not bad, "C6", "元信息字段齐备" if not bad else "问题卡片：" + "; ".join(bad[:6]))


def check_appendix_refs(cards: dict[str, dict], appendix_texts: dict[str, str]) -> None:
    bad: list[str] = []
    for tid, card in cards.items():
        refs = re.findall(r"附录\s*([ABC])\s*§\s*(T-\d{3})", card["body"])
        if not refs:
            continue
        if "无附录" in card["body"]:
            continue  # 新增任务的卡片自带步骤，附录引用仅为旁注
        # 卡片自身编号的引用优先；其余引用视为对其它任务步骤的旁注，只校验附录文件里确有该小节
        own = [(l, r) for l, r in refs if r == tid]
        if own:
            letter, ref = own[0]
        else:
            letter, ref = refs[0]
        if f"### {ref}" not in appendix_texts.get(letter, ""):
            bad.append(f"{tid}(附录 {letter} 缺 §{ref})")
        elif not own:
            bad.append(f"{tid}(未标注自身附录引用，只引用 {letter} §{ref})")
    record(not bad, "C7", "附录引用有效" if not bad else "; ".join(bad[:6]))


def check_stale_wording(scan_text: str, overview: str) -> None:
    found = [p for p in STALE_PATTERNS if p in scan_text]
    if "十条" not in overview:
        found.append("§4.1.5 未写「十条」")
    if "九条" not in overview:
        found.append("§4.2.7 未写「九条」")
    record(not found, "C8", "版本与验收口径一致" if not found else "陈旧表述：" + "; ".join(found))


def print_stats(cards: dict[str, dict]) -> None:
    unattended: dict[str, int] = {}
    batches: dict[str, int] = {}
    deltas: dict[str, int] = {}
    groups: dict[str, int] = {}
    for card in cards.values():
        levels = [x.strip() for x in re.split(r"[/／]", card["unattended"]) if x.strip()]
        for lv in levels:
            unattended[lv] = unattended.get(lv, 0) + 1
        batches[card["batch"]] = batches.get(card["batch"], 0) + 1
        if card["delta"]:
            deltas[card["delta"]] = deltas.get(card["delta"], 0) + 1
        if card["group"]:
            groups[card["group"]] = groups.get(card["group"], 0) + 1

    print("-" * 60)
    print(f"任务总数: {len(cards)}")
    print("无人值守度: " + " | ".join(f"{k}={v}" for k, v in sorted(unattended.items())))
    primary: dict[str, int] = {}
    for card in cards.values():
        lv = (re.split(r"[/／]", card["unattended"])[0] or "?").strip()
        primary[lv] = primary.get(lv, 0) + 1
    print("主级别(取第一标记): " + " | ".join(f"{k}={v}" for k, v in sorted(primary.items())))
    print("按批次: " + " | ".join(f"{k}={v}" for k, v in batches.items()))
    print(f"并行组数: {len(groups)}（最大并发建议 4）")
    new_cnt = sum(1 for c in cards.values() if "（新增）" in c["delta"])
    print(f"新增任务: {new_cnt}（{', '.join(t for t in NEW_TASKS)}）")
    print(f"含增补/修订标注的卡片: {sum(1 for c in cards.values() if c['delta'] and '新增' not in c['delta'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="WorkNexus-DSH 任务拆分门禁")
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    parser.add_argument("--stats", action="store_true", help="额外输出任务分布统计")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    card_text = read_text(root / CARD_FILE)
    overview = read_text(root / OVERVIEW_FILE)
    spec = read_text(root / SPEC_FILE)
    report = read_text(root / REPORT_FILE)
    appendix_texts = {k: read_text(root / v) for k, v in APPENDICES.items()}

    print("=" * 60)
    print("WorkNexus-DSH 任务拆分门禁（v3.0 / 需求基线 v1.2）")
    print("=" * 60)

    fatal = []
    for label, text, path in [
        ("派发卡", card_text, CARD_FILE),
        ("总览", overview, OVERVIEW_FILE),
        ("需求说明书", spec, SPEC_FILE),
        ("检查报告", report, REPORT_FILE),
    ]:
        if not text:
            fatal.append(f"{label}缺失：{path}")

    if fatal:
        for item in fatal:
            print(f"[FAIL] {item}")
        print("\n结果: 0 [OK] / %d [FAIL]" % len(fatal))
        return 1

    cards = parse_cards(card_text)
    corpus = overview + card_text
    scan_text = overview + card_text + "".join(appendix_texts.values())

    check_requirement_coverage(spec, card_text, overview)
    check_chapter_anchors(corpus)
    check_task_ids(cards)
    check_dependencies(cards)
    check_required_blocks(cards)
    check_meta_fields(cards)
    check_appendix_refs(cards, appendix_texts)
    check_stale_wording(scan_text, overview)

    ok_count = sum(1 for ok, _, _ in RESULTS if ok)
    for ok, code, detail in RESULTS:
        print(f"[{'OK' if ok else 'FAIL'}] {code} {detail}")

    if args.stats:
        print_stats(cards)

    print("-" * 60)
    print(f"结果: {ok_count} [OK] / {len(RESULTS) - ok_count} [FAIL]")
    return 0 if ok_count == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
