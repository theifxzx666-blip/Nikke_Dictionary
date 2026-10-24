#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 GameKee 加点页缓存解析「技能 Lv1~Lv10 全档位」。

输入：cache/gamekee_content_details/content_<contentId>.json
      （content 字段是一段被 JSON 序列化两次的 baseData 二维表）

输出：data/character_repository/sources/gamekee_skills_<yyyymmdd>/skills_by_content.json

只做解析，不改词典。写入由 apply_skill_level10.py 负责。
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "gamekee_content_details"

SECTION_LABELS = {
    "技能1名称": "skill1",
    "技能2名称": "skill2",
    "爆裂技能名称": "burstSkill",
    "爆裂技能": "burstSkill",
}
FIELD_LABELS = {
    "冷却时间": "cooldown",
    "技能类型": "type",
    "技能描述": "_desc_anchor",
    "珍藏品强化": "_treasure_anchor",
    "技能描述（lv10)）": "treasureLv10",
    "名词解释": "_glossary_anchor",
}
STOP_LABELS = {"普攻", "珍藏品名称", "名词解释"}
LV_RE = re.compile(r"^lv\s*(\d{1,2})$", re.I)


def cell_text(cell) -> str:
    if isinstance(cell, dict):
        v = cell.get("value")
        return v if isinstance(v, str) else ""
    return cell if isinstance(cell, str) else ""


def row_texts(row) -> list[str]:
    if not isinstance(row, list):
        return []
    return [cell_text(c) for c in row]


def load_rows(path: Path) -> list[list[str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    content = raw.get("content")
    if isinstance(content, str):
        content = json.loads(content)
    rows = content.get("baseData") or []
    return [row_texts(r) for r in rows]


def parse(path: Path) -> dict:
    rows = load_rows(path)
    base: dict = {"contentId": int(path.stem.split("_")[-1]), "charName": "", "panel": {}, "skills": {}, "normalAttack": {}, "treasure": {}}

    section = None
    for texts in rows:
        if not texts:
            continue
        label = texts[0].strip()
        values = [t for t in texts[1:] if isinstance(t, str) and t.strip()]

        if label == "角色名称" and values:
            base["charName"] = values[0].strip()
            continue

        if label in SECTION_LABELS:
            section = SECTION_LABELS[label]
            base["skills"].setdefault(
                section,
                {"name": "", "type": "", "cooldown": "", "icon": "", "levels": {}, "treasureLv10": "", "nameLabel": label},
            )
            if values:
                base["skills"][section]["name"] = values[0].strip()
            # 图标在紧随其后的「技能X图标」行，稍后按 section 回填
            continue

        if label in ("技能1图标", "技能2图标", "爆裂技能图标"):
            key = {"技能1图标": "skill1", "技能2图标": "skill2", "爆裂技能图标": "burstSkill"}[label]
            if values:
                base["skills"].setdefault(key, {"name": "", "type": "", "cooldown": "", "icon": "", "levels": {}, "treasureLv10": ""})
                base["skills"][key]["icon"] = values[0].strip()
            continue

        if label == "普攻":
            section = "normalAttack"
            continue
        if section == "normalAttack":
            if label == "珍藏品名称":
                section = None  # 落到下方珍藏品分支，不 continue
            else:
                if label == "武器类型" and values:
                    base["normalAttack"]["weaponType"] = values[0].strip()
                elif label == "普攻描述" and values:
                    base["normalAttack"]["desc"] = values[0].strip()
                elif label == "武器数据" and values:
                    pairs = {values[i].strip(): values[i + 1].strip() for i in range(0, len(values) - 1, 2)}
                    base["normalAttack"]["stats"] = {k: v for k, v in pairs.items() if k}
                elif label == "最大装弹数":
                    pairs = {texts[i].strip(): texts[i + 1].strip() for i in range(0, len(texts) - 1, 2)}
                    base["normalAttack"]["stats"] = {k: v for k, v in pairs.items() if k}
                continue

        if label == "珍藏品名称":
            if values:
                base["treasure"]["name"] = values[0].strip()
            section = "treasure"
            continue
        if label == "珍藏品稀有度" and values:
            base["treasure"]["rarity"] = values[0].strip()
            continue
        if label == "珍藏品数据" and values:
            base["treasure"]["stats"] = {values[i]: values[i + 1] for i in range(0, len(values) - 1, 2)}
            continue
        if label == "珍藏品简介" and values:
            base["treasure"]["desc"] = values[0].strip()
            continue

        m = LV_RE.match(label)
        if m and section in ("skill1", "skill2", "burstSkill"):
            lvl = int(m.group(1))
            if values and values[0].strip() not in ("/", ""):
                base["skills"][section]["levels"][str(lvl)] = values[0]
            continue

        if section in ("skill1", "skill2", "burstSkill"):
            field = FIELD_LABELS.get(label)
            if field == "treasureLv10" and values:
                base["skills"][section]["treasureLv10"] = values[0]
            elif field in ("cooldown", "type") and values:
                base["skills"][section][field] = values[0].strip()
            elif label in STOP_LABELS:
                section = None

    return base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-date", default=date.today().strftime("%Y%m%d"))
    args = ap.parse_args()

    files = sorted(CACHE.glob("content_*.json"))
    out: dict = {"generatedAt": date.today().isoformat(), "source": "GameKee 加点页缓存 cache/gamekee_content_details", "characters": {}}
    bad = []
    for p in files:
        try:
            rec = parse(p)
        except Exception as exc:  # noqa: BLE001
            bad.append((p.name, f"{type(exc).__name__}: {exc}"))
            continue
        if rec["charName"] or rec["skills"]:
            out["characters"][str(rec["contentId"])] = rec

    with_three = sum(1 for r in out["characters"].values() if len(r["skills"]) == 3)
    with_lv10 = sum(
        1
        for r in out["characters"].values()
        for s in r["skills"].values()
        if "10" in s["levels"]
    )
    out["stats"] = {
        "files": len(files),
        "parsed": len(out["characters"]),
        "withAllThreeSkills": with_three,
        "skillBlocksWithLv10": with_lv10,
        "failed": bad,
    }

    dest = ROOT / "data" / "character_repository" / "sources" / f"gamekee_skills_{args.out_date}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "skills_by_content.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(out["stats"], ensure_ascii=False, indent=1))
    print("out:", dest / "skills_by_content.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
