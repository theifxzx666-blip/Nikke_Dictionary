#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把技能面板统一到 Lv10，并保留 Lv1~Lv10 全档位。

读：data/character_repository/sources/gamekee_skills_<date>/skills_by_content.json
写：data/nikke_character_dictionary_enhanced.json

写入规则：
- skills.<k>.effect        ← Lv10 基础描述（主面板，交付口径）
- skills.<k>.level         ← 10
- skills.<k>.levels        ← {"1": "...", ..., "10": "..."} 全档位
- skills.<k>.treasureEffect← 珍藏品强化 Lv10（与 base 不同才写）
- skills.<k>.name/type/cooldown ← 名称/类型/冷却
- normalAttack             ← 补 desc / stats / maxAmmo
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DICT = ROOT / "data" / "nikke_character_dictionary_enhanced.json"
ARCHIVE = ROOT / "data" / "archive"

SKILL_KEYS = ("skill1", "skill2", "burstSkill")


def find_source() -> Path:
    cands = sorted((ROOT / "data" / "character_repository" / "sources").glob("gamekee_skills_*/skills_by_content.json"))
    if not cands:
        raise SystemExit("找不到 skills_by_content.json，先跑 extract_skill_levels_from_gamekee.py")
    return cands[-1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写入；默认 dry-run")
    args = ap.parse_args()

    src_path = find_source()
    src = json.loads(src_path.read_text(encoding="utf-8"))["characters"]
    rows = json.loads(DICT.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    changed = {"skillsLv10": 0, "skillsName": 0, "treasureKept": 0, "normalAttack": 0, "missing": []}

    for row in rows:
        cid = str(row.get("gamekeeContentId") or "")
        rec = src.get(cid)
        if not rec:
            changed["missing"].append(row["name"])
            continue

        skills = row.get("skills")
        if not isinstance(skills, dict):
            skills = {}
            row["skills"] = skills

        for key in SKILL_KEYS:
            s = rec["skills"].get(key)
            if not s:
                continue
            levels = s.get("levels") or {}
            lv10 = (levels.get("10") or "").strip()
            if not lv10:
                continue

            dst = skills.get(key)
            if not isinstance(dst, dict):
                dst = {}
                skills[key] = dst

            if (dst.get("name") or "").strip() != (s.get("name") or "").strip():
                dst["name"] = (s.get("name") or "").strip()
                changed["skillsName"] += 1
            # 已知脏值修正：个别条目把「冷却时间」的解释段误塞进 cooldown
            cd = (s.get("cooldown") or "").strip()
            if cd and len(cd) <= 8:
                dst["cooldown"] = cd
            if (s.get("type") or "").strip():
                dst["type"] = s["type"].strip()
            if (s.get("icon") or "").strip():
                dst["iconUrl"] = s["icon"].strip()

            if dst.get("effect") != lv10:
                dst["effect"] = lv10
                changed["skillsLv10"] += 1
            dst["level"] = 10
            dst["levels"] = {str(i): levels.get(str(i), "") for i in range(1, 11)}

            treasure = (s.get("treasureLv10") or "").strip()
            if treasure and treasure != lv10:
                dst["treasureEffect"] = treasure
                changed["treasureKept"] += 1
            else:
                dst.pop("treasureEffect", None)

        na = rec.get("normalAttack") or {}
        if na.get("desc"):
            cur = row.get("normalAttack")
            if not isinstance(cur, dict):
                cur = {}
                row["normalAttack"] = cur
            touched = False
            if cur.get("desc") != na["desc"]:
                cur["desc"] = na["desc"]
                touched = True
            stats = na.get("stats") or {}
            if stats and cur.get("weaponStats") != stats:
                cur["weaponStats"] = stats
                touched = True
            ammo = stats.get("最大装弹数")
            if ammo and cur.get("ammo") != ammo:
                cur["ammo"] = ammo
                touched = True
            if na.get("weaponType") and not cur.get("type"):
                cur["type"] = na["weaponType"]
                touched = True
            cur.pop("optimalRange", None)
            if touched:
                changed["normalAttack"] += 1

        row["skillLevelBasis"] = f"GameKee 加点页 Lv10（快照 {src_path.parent.name}）"
        row["skillUpdatedAt"] = today

    print(json.dumps({k: (v if not isinstance(v, list) else f"{len(v)} 条") for k, v in changed.items()}, ensure_ascii=False, indent=1))
    print("source:", src_path)

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 落地。")
        return 0

    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup = ARCHIVE / f"nikke_character_dictionary_enhanced.bak-{stamp}.json"
    shutil.copy2(DICT, backup)
    DICT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("backup:", backup)
    print("written:", DICT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
