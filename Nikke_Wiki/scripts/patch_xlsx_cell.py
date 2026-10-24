# -*- coding: utf-8 -*-
"""定点修正 xlsx 中个别单元格的文字（XML 层手术，不重写工作簿）。

为什么不用 openpyxl 保存：该工作簿含 886 个媒体文件（头像/立绘，六张 sheet 的
drawing 关系），openpyxl 整本回写有丢图与锚点漂移风险。这里只在 zip 内替换
目标 sheet 的某个单元格共享字符串索引，其余条目按原字节、原压缩方式写回。

用法：
    python scripts/patch_xlsx_cell.py --dry-run
    python scripts/patch_xlsx_cell.py --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
XLSX_PATH = PROJECT_ROOT / "正式产物" / "nikke_character_dictionary_with_images.xlsx"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"

# (sheet 名, 单元格, 期望旧值, 新值)
PATCHES = [("角色字典", "C159", "沃伦姆", "沃纶姆")]


def sheet_files(zf: zipfile.ZipFile) -> dict[str, str]:
    """sheet 名 -> zip 内 worksheet 路径。"""
    wb = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rel_map = dict(
        re.findall(r'Id="(rId\d+)"[^>]*?Target="(worksheets/[^"]+)"', rels)
    )
    out: dict[str, str] = {}
    for name, rid in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="(rId\d+)"', wb):
        target = rel_map.get(rid)
        if target:
            out[name] = f"xl/{target}"
    return out


def read_si(zf: zipfile.ZipFile) -> list[str]:
    ss = zf.read("xl/sharedStrings.xml").decode("utf-8")
    return [
        re.sub(r"<[^>]+>", "", m)
        for m in re.findall(r"<si>(.*?)</si>", ss, re.S)
    ]


def cell_ref(xml: str, ref: str) -> re.Match | None:
    return re.search(rf'<c r="{ref}"[^>]*>.*?</c>', xml, re.S)


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not (a.dry_run or a.apply):
        ap.error("需要 --dry-run 或 --apply")

    with zipfile.ZipFile(XLSX_PATH) as zf:
        files = sheet_files(zf)
        si = read_si(zf)
        # 计划：每处待改单元格找出目标共享字符串索引
        plan: list[tuple[str, str, int, int, str]] = []
        for sheet, ref, old, new in PATCHES:
            path = files[sheet]
            xml = zf.read(path).decode("utf-8")
            m = cell_ref(xml, ref)
            if not m:
                raise SystemExit(f"{sheet}!{ref} 不存在")
            idx_old = int(re.search(r"<v>(\d+)</v>", m.group(0)).group(1))
            actual = si[idx_old]
            if actual != old:
                raise SystemExit(f"{sheet}!{ref} 现值「{actual}」≠ 期望旧值「{old}」")
            try:
                idx_new = si.index(new)
            except ValueError:
                raise SystemExit(f"共享字符串缺少「{new}」，本脚本不支持新增字符串")
            plan.append((sheet, ref, idx_old, idx_new, m.group(0)))

        for sheet, ref, io, inn, raw in plan:
            print(f"{sheet}!{ref}: si[{io}]「{si[io]}」 -> si[{inn}]「{si[inn]}」")

        if a.dry_run:
            print("\n[dry-run] 未写入")
            return 0

        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = ARCHIVE_DIR / f"{XLSX_PATH.stem}_{stamp}{XLSX_PATH.suffix}"
        shutil.copy2(XLSX_PATH, backup)
        print(f"已备份: {backup}")

        replace: dict[str, str] = {}
        for sheet, ref, io, inn, raw in plan:
            path = files[sheet]
            xml = replace.get(path) or zf.read(path).decode("utf-8")
            new_cell = raw.replace(f"<v>{io}</v>", f"<v>{inn}</v>")
            replace[path] = xml.replace(raw, new_cell, 1)

        tmp = XLSX_PATH.with_name(XLSX_PATH.stem + ".patching" + XLSX_PATH.suffix)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
            for item in zf.infolist():
                data = (
                    replace[item.filename].encode("utf-8")
                    if item.filename in replace
                    else zf.read(item.filename)
                )
                zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
                zi.compress_type = item.compress_type
                zi.external_attr = item.external_attr
                out.writestr(zi, data)

    tmp.replace(XLSX_PATH)  # 原子替换（避开 safe-delete 层）
    print(f"已写入: {XLSX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
