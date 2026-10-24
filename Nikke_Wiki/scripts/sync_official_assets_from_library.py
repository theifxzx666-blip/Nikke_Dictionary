#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把拆包资源库的官方素材挂到词典条目上。

素材库：F:\\Codex\\Nikke\\Nikke_Skills\\拆包\\00_资源库
  角色头像\\<中文名>_c<id>_<NN>_mi_uc_tex.png   256x512 头像
  角色立绘\\<中文名>_c<id>_<NN>.png              715x961 全身立绘
  角色立绘HD\\<中文名>_c<id>_<NN>_uc_tex.png     2048x2048 HD 立绘

落位：data\\character_repository\\assets\\official\\<slug>\\{portrait,fullbody,hd}.png
     默认硬链接（同一磁盘零占用），失败则复制。

写词典字段：
  officialCode / officialPortraitFile / officialFullBodyFile / officialHdFile
  officialAssetStatus / officialAssetSource
另外：localPortraitFile 缺失时用官方头像补齐。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "data" / "nikke_character_dictionary_enhanced.json"
DEST = ROOT / "data" / "character_repository" / "assets" / "official"
ARCHIVE = ROOT / "data" / "archive"
LIB = Path(r"F:\Codex\Nikke\Nikke_Skills\拆包\00_资源库")

SOURCES = (
    ("portrait", ("头像", "角色头像"), re.compile(r"^(?P<name>.+)_c(?P<id>\d+)_(?P<var>\d+)_mi_uc_tex\.png$", re.I)),
    ("fullbody", ("立绘", "角色立绘"), re.compile(r"^(?P<name>.+)_c(?P<id>\d+)_(?P<var>\d+)\.png$", re.I)),
    ("hd", ("立绘HD", "角色立绘HD"), re.compile(r"^(?P<name>.+)_c(?P<id>\d+)_(?P<var>\d+)_uc_tex\.png$", re.I)),
)
ICON_RE = re.compile(r"^si[_-]c(\d+)_(\d+)_", re.I)


def locate_dir(names: tuple[str, ...]) -> Path | None:
    """资源库目录名曾从「角色头像/角色立绘」改为「01_角色/头像/立绘」等，两种都认。"""
    for name in names:
        direct = LIB / name
        if direct.is_dir():
            return direct
    for name in names:
        for hit in LIB.rglob(name):
            if hit.is_dir():
                return hit
    return None


def index_library() -> tuple[dict, dict]:
    by_code: dict[tuple[int, str], dict] = {}
    by_name: dict[str, dict] = {}
    for kind, sub_names, pat in SOURCES:
        folder = locate_dir(sub_names)
        if not folder:
            print(f"[warn] 未找到素材目录 {sub_names}，跳过 {kind}")
            continue
        for p in folder.glob("*.png"):
            m = pat.match(p.name)
            if not m:
                continue
            cid, var = int(m.group("id")), m.group("var")
            key = (cid, var)
            by_code.setdefault(key, {})[kind] = p
            by_name.setdefault(m.group("name"), {})[kind] = p
    return by_code, by_name


def link(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    by_code, by_name = index_library()
    rows = json.loads(DICT.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    stats = {"matchedCode": 0, "matchedName": 0, "noAsset": [], "linked": {}, "filledPortrait": 0}
    plan = []

    for row in rows:
        slug = Path(row.get("localIconFile") or "").stem or row.get("name", "").lower()
        icon_id = row.get("iconId") or ""
        m = ICON_RE.match(icon_id)
        hit = None
        code = ""
        if m:
            cid, var = int(m.group(1)), m.group(2)
            hit = by_code.get((cid, var)) or by_code.get((cid, "00"))
            code = f"c{cid}_{var}"
            if hit:
                stats["matchedCode"] += 1
        if not hit:
            cn = (row.get("cnName") or "").strip()
            if cn and cn in by_name:
                hit = by_name[cn]
                stats["matchedName"] += 1
                code = code or Path(next(iter(hit.values()))).name
        if not hit:
            stats["noAsset"].append(row["name"])
            row["officialAssetStatus"] = "资源库未收录"
            continue

        rel = []
        for kind in ("portrait", "fullbody", "hd"):
            src = hit.get(kind)
            if not src:
                continue
            dst = DEST / slug / f"{kind}.png"
            plan.append((kind, src, dst))
            row[f"official{ {'portrait':'Portrait','fullbody':'FullBody','hd':'Hd'}[kind] }File"] = str(dst).replace("\\", "/")
            rel.append(kind)
            stats["linked"][kind] = stats["linked"].get(kind, 0) + 1
        row["officialCode"] = code
        row["officialAssetStatus"] = "已收录:" + "/".join(rel)
        row["officialAssetSource"] = "拆包资源库 00_资源库（国服客户端原始纹理）"
        row["officialAssetUpdatedAt"] = today

        if not row.get("localPortraitFile") and "portrait" in hit:
            row["localPortraitFile"] = str(DEST / slug / "portrait.png").replace("\\", "/")
            row["localPortraitSource"] = "拆包资源库官方头像（补齐）"
            stats["filledPortrait"] += 1

    if args.apply:
        for kind, src, dst in plan:
            link(src, dst)
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = ARCHIVE / f"nikke_character_dictionary_enhanced.bak-{stamp}.json"
        shutil.copy2(DICT, backup)
        DICT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print("backup:", backup)

    print(json.dumps({
        "词典条目": len(rows),
        "按id匹配": stats["matchedCode"],
        "按中文名匹配": stats["matchedName"],
        "未收录": len(stats["noAsset"]),
        "未收录名单": stats["noAsset"],
        "各类型落位": stats["linked"],
        "补齐立绘": stats["filledPortrait"],
        "应用": bool(args.apply),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
