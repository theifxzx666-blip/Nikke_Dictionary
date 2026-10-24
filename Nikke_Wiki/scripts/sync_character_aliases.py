# -*- coding: utf-8 -*-
"""把 xlsx 词典里手工补的别名同步进机器人可读的别名表。

数据流（单向）：
    正式产物/nikke_character_dictionary_with_images.xlsx
        「角色字典」别名列 + 「全汉化」常用别名列   ← 两表**取并集**，你维护任一处都生效
        ↓ 合并（xlsx 显式填写的为主，母体/机器人侧既有别名只做补入，不覆盖）
    data/nikke_character_aliases.json   ← 机器人 WikiIndex 启动即读

键为英文名（与母体格式一致），值含中文名本体，供 index.py 的 by_alias 归一化。

用法：
    python scripts/sync_character_aliases.py --dry-run
    python scripts/sync_character_aliases.py --apply
    python scripts/sync_character_aliases.py --apply --write-dict   # 顺带回灌词典 aliases
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
XLSX_PATH = PROJECT_ROOT / "正式产物" / "nikke_character_dictionary_with_images.xlsx"
ALIASES_JSON = PROJECT_ROOT / "data" / "nikke_character_aliases.json"
DICTIONARY_JSON = PROJECT_ROOT / "data" / "nikke_character_dictionary_enhanced.json"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"
BOT_EXTRA_ALIASES = Path(
    "F:/AI/Nikke/[2]Skills/05_应用与服务/Nikke_Bot/host/data/character_aliases_extra.json"
)

# 两处别名来源：(sheet 名, 英文名列, 中文名列, 别名列)，索引从 0 起
SHEETS: tuple[tuple[str, int, int, int], ...] = (
    ("角色字典", 1, 2, 3),
    ("全汉化", 13, 2, 3),
)
# 用户在不同行用了不同分隔符，全部视为分隔
SPLIT_PATTERN = re.compile(r"[；;|｜、,，/／]+")

# 机器人侧补充表用的是旧译名作键，与 xlsx 现名不同，需显式对齐
# （去标点/大小写后仍不相等的少数几个，其余靠 normalize 与别名反查自动匹配）
EXPLICIT_KEY_ALIASES = {
    "爱德：特务兔女郎": "爱德：特工兔女郎",
}


def parse_aliases(raw: Any) -> list[str]:
    """按多种分隔符拆分别名单元格，去空白、去重、保序。"""
    out: list[str] = []
    for part in SPLIT_PATTERN.split(str(raw or "")):
        item = part.strip()
        if item and item not in out:
            out.append(item)
    return out


def normalize(text: str) -> str:
    """去标点、去空格、统一小写，用于跨表名称比对。"""
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def load_xlsx_rows() -> tuple[
    list[tuple[str, str, list[str]]],
    dict[str, int],
    dict[tuple[str, str], str],
]:
    """读「角色字典」与「全汉化」两处别名列并取并集。

    返回 (行数据, 各表条数, 每条别名首个来源表)。英文名做键；中文名以先出现者为准
    （「角色字典」在前，故为权威表），两表中文名不同会打印告警。
    """
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    missing = [s for s, *_ in SHEETS if s not in wb.sheetnames]
    if missing:
        raise SystemExit(f"xlsx 缺少工作表 {missing}：{wb.sheetnames}")

    order: list[str] = []
    cn_of: dict[str, str] = {}
    aliases_of: dict[str, list[str]] = {}
    src_of: dict[tuple[str, str], str] = {}
    sheet_raw: dict[str, int] = {}
    name_diff: list[str] = []

    for sheet, col_en, col_cn, col_alias in SHEETS:
        raw = 0
        for row in wb[sheet].iter_rows(min_row=2, values_only=True):
            name = str(row[col_en] or "").strip()
            if not name:
                continue
            cn = str(row[col_cn] or "").strip()
            if name not in aliases_of:
                order.append(name)
                aliases_of[name] = []
                cn_of[name] = cn
            elif cn and cn_of[name] and cn != cn_of[name]:
                name_diff.append(f"{name}: 「{cn_of[name]}」({SHEETS[0][0]}) ≠ 「{cn}」({sheet})，保留前者")
            elif cn and not cn_of[name]:
                cn_of[name] = cn
            for alias in parse_aliases(row[col_alias]):
                raw += 1
                src_of.setdefault((name, alias), sheet)
                if alias not in aliases_of[name]:
                    aliases_of[name].append(alias)
        sheet_raw[sheet] = raw

    wb.close()
    rows = [(n, cn_of[n], aliases_of[n]) for n in order]
    if not rows:
        raise SystemExit("xlsx 没有可用数据行")
    for line in name_diff:
        print(f"  ! 中文名不一致 {line}")
    return rows, sheet_raw, src_of


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def resolve_extra_key(
    key: str,
    cn_of: dict[str, str],
    alias_owner: dict[str, str],
) -> str | None:
    """把补充表的键（可能是旧译名/别名）解析成当前英文名。"""
    target_cn = EXPLICIT_KEY_ALIASES.get(key, key)
    for en, cn in cn_of.items():
        if cn == target_cn:
            return en
    norm = normalize(target_cn)
    for en, cn in cn_of.items():
        if cn and normalize(cn) == norm:
            return en
    # 键本身就是某角色的别名（如「零」= 丽、「真理」= 玛丽）
    return alias_owner.get(target_cn)


def build(
    rows: list[tuple[str, str, list[str]]],
    src_of: dict[tuple[str, str], str] | None = None,
    verbose: bool = False,
) -> tuple[dict[str, list[str]], list[str], dict[str, int]]:
    src_of = src_of or {}
    names = [r[0] for r in rows]
    cn_of = {r[0]: r[1] for r in rows}
    xlsx_explicit = {r[0]: set(r[2]) for r in rows}

    # 规范名归属：别名恰好等于某角色中文名/英文名时，归该角色
    owner_of: dict[str, str] = {}
    for name in names:
        owner_of[name] = name
    for en, cn in cn_of.items():
        if cn:
            owner_of.setdefault(cn, en)

    # 别名 -> 角色（用于把补充表的旧键反查成当前角色）
    alias_owner: dict[str, str] = {}
    for en, cn in cn_of.items():
        for alias in xlsx_explicit[en]:
            alias_owner.setdefault(alias, en)

    merged: dict[str, list[str]] = {name: list(aliases) for name, _, aliases in rows}
    added_log: list[str] = []

    def merge_alias(target: str, alias: str, source: str) -> None:
        alias = str(alias).strip()
        if not alias or alias in merged[target]:
            return
        merged[target].append(alias)
        added_log.append(f"{alias} -> {target}（{source}）")

    # 母体：键为英文名
    mom_added = 0
    mom = load_json(ALIASES_JSON) or {}
    if isinstance(mom, dict):
        for formal, alias_list in mom.items():
            if not isinstance(alias_list, list):
                continue
            target = formal if formal in merged else None
            if target is None:
                target = next((en for en, cn in cn_of.items() if cn == formal), None)
            if target is None:
                continue
            for alias in alias_list:
                before = len(merged[target])
                merge_alias(target, alias, "母体")
                mom_added += len(merged[target]) - before

    # 机器人侧补充表：键多为中文名/旧译名
    extra_added = 0
    extra_unmatched: list[str] = []
    extra = load_json(BOT_EXTRA_ALIASES) or {}
    if isinstance(extra, dict):
        for formal, alias_list in extra.items():
            if not isinstance(alias_list, list):
                continue
            target = resolve_extra_key(str(formal).strip(), cn_of, alias_owner)
            if not target:
                extra_unmatched.append(str(formal))
                continue
            for alias in alias_list:
                before = len(merged[target])
                merge_alias(target, alias, "机器人补充")
                extra_added += len(merged[target]) - before

    # 每个角色必须能用自己的中英文名召回
    for name, cn in cn_of.items():
        bucket = merged[name]
        for self_name in (cn, name):
            if self_name and self_name not in bucket:
                bucket.insert(0, self_name)

    # 冲突裁决：一个别名只保留给一个角色
    alias_owners: dict[str, list[str]] = {}
    for name, bucket in merged.items():
        for alias in bucket:
            alias_owners.setdefault(alias, []).append(name)

    conflicts: list[str] = []
    for alias, owners in alias_owners.items():
        if len(owners) < 2:
            continue
        canon = owner_of.get(alias)
        if canon and canon in owners:
            winner = canon
            reason = "规范名归属"
        else:
            explicit = [n for n in owners if alias in xlsx_explicit[n]]
            if len(explicit) == 1:
                winner = explicit[0]
                reason = f"xlsx 显式指定（{src_of.get((winner, alias), '?')}）"
            elif len(explicit) > 1:
                # 两表都写了同一别名 → 「角色字典」优先，其次按行序
                ranked = sorted(
                    explicit,
                    key=lambda n: (
                        0 if src_of.get((n, alias)) == SHEETS[0][0] else 1,
                        names.index(n),
                    ),
                )
                winner = ranked[0]
                reason = "两表都显式声明，按角色字典优先"
            else:
                winner = owners[0]
                reason = "均非显式，取首个"
        for name in owners:
            if name != winner:
                merged[name].remove(alias)
        conflicts.append(f"{alias}：{owners} → 保留「{winner}」（{reason}）")

    stats = {
        "characters": len(rows),
        "from_xlsx": sum(len(a) for _, _, a in rows),
        "from_mother": mom_added,
        "from_bot_extra": extra_added,
        "extra_unmatched": len(extra_unmatched),
    }
    for key in extra_unmatched:
        conflicts.append(f"[补充表键未匹配] {key} — 该键下别名未并入")
    if verbose:
        for line in added_log:
            print(f"  + {line}")
    return merged, conflicts, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 xlsx 别名到机器人别名表")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只打印统计与冲突，不写文件")
    mode.add_argument("--apply", action="store_true", help="写入别名表（先备份旧文件）")
    parser.add_argument(
        "--write-dict",
        action="store_true",
        help="同时把合并结果回灌词典 aliases 字段（| 分隔），避免重跑导出脚本时覆盖表内别名",
    )
    parser.add_argument("--verbose", action="store_true", help="打印每条补入别名的来源")
    args = parser.parse_args()
    if not (args.dry_run or args.apply):
        parser.error("需要 --dry-run 或 --apply")

    rows, sheet_raw, src_of = load_xlsx_rows()
    merged, conflicts, stats = build(rows, src_of=src_of, verbose=args.verbose)
    total_aliases = sum(len(v) for v in merged.values())

    print(f"角色行        : {stats['characters']}")
    for sheet, count in sheet_raw.items():
        print(f"  · {sheet} {('别名' if sheet == '角色字典' else '常用别名')}列 : {count} 条")
    print(f"两表并集      : {stats['from_xlsx']} 条（去重后）")
    print(f"母体补入      : {stats['from_mother']}")
    print(f"机器人侧补入  : {stats['from_bot_extra']}")
    print(f"合并后总条数  : {total_aliases}")
    print(f"冲突裁决      : {len(conflicts)}")
    for line in conflicts:
        print(f"  - {line}")

    if args.dry_run:
        print("\n[dry-run] 未写入任何文件")
        return 0

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if ALIASES_JSON.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = ARCHIVE_DIR / f"nikke_character_aliases_{stamp}.json"
        shutil.copy2(ALIASES_JSON, backup)
        print(f"\n已备份旧表: {backup}")

    payload = {name: aliases for name, aliases in merged.items() if aliases}
    with ALIASES_JSON.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"已写入: {ALIASES_JSON}（{len(payload)} 键 / {total_aliases} 别名）")

    if args.write_dict:
        # 只回灌表内并集（不含母体/机器人黑话），这样导出脚本再重填两个别名列时
        # 结果与表内完全一致，既不会清掉手工别名，也不会把黑话灌进表
        write_back_dictionary(merged, {r[0]: r[2] for r in rows})
    return 0


def write_back_dictionary(
    merged: dict[str, list[str]],
    table_aliases: dict[str, list[str]] | None = None,
) -> None:
    """把 xlsx 表内别名（两表并集）写回词典 aliases 字段（`|` 分隔字符串）。

    导出脚本 export_nikke_character_tables.py 直接用该字段填 xlsx 两个别名列，
    不回灌的话，表里手工补的别名会在下次重导出时被清回词典旧值。

    只写 `table_aliases`（表内并集）而**不写** `merged`（含母体旧表与机器人黑话），
    保证「词典 → 导出 → 表」与「表 → 同步 → 词典」互为逆运算。
    """
    source = table_aliases if table_aliases is not None else merged
    records = load_json(DICTIONARY_JSON)
    if not isinstance(records, list):
        raise SystemExit(f"词典格式异常: {DICTIONARY_JSON}")

    # 原文件用 CRLF，写回时保持，避免整文件 diff
    raw = DICTIONARY_JSON.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"

    changed = 0
    normalized = 0
    for rec in records:
        name = str(rec.get("name") or "").strip()
        if name not in source:
            continue          # 表里没有这个角色，保留词典原值
        aliases = source[name]
        text = "|".join(aliases)
        before = rec.get("aliases")
        if not isinstance(before, str):
            normalized += 1          # 个别记录曾是 JSON 数组，统一成 | 分隔字符串
        if str(before or "") != text:
            rec["aliases"] = text
            changed += 1
    if not changed:
        print("词典 aliases 已是最新，无需回灌")
        return
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ARCHIVE_DIR / f"{DICTIONARY_JSON.stem}_{stamp}{DICTIONARY_JSON.suffix}"
    shutil.copy2(DICTIONARY_JSON, backup)
    text = json.dumps(records, ensure_ascii=False, indent=1)
    if nl != "\n":
        text = text.replace("\n", nl)
    with DICTIONARY_JSON.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text + nl)
    print(
        f"已回灌词典: {DICTIONARY_JSON}（改动 {changed} 条"
        f"{'，其中 ' + str(normalized) + ' 条由数组规范化为字符串' if normalized else ''}"
        f"，备份 {backup.name}）"
    )


if __name__ == "__main__":
    raise SystemExit(main())
