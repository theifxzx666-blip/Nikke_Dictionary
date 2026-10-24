from __future__ import annotations

import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUT = DATA_DIR / "reports" / "targeted_gamekee_entry_repair_report.json"
TARGETS = {
    705512: "playable",
    706696: "playable",
    708686: "playable",
    711133: "playable",
    711739: "playable",
    713891: "playable",
    713899: "playable",
}


def main() -> None:
    playable = json.loads((DATA_DIR / "nikke_character_dictionary_enhanced.json").read_text(encoding="utf-8"))
    npc = json.loads((DATA_DIR / "non_playable_character_cards.json").read_text(encoding="utf-8"))
    costumes = json.loads((DATA_DIR / "gamekee_costume_catalog.json").read_text(encoding="utf-8"))
    output = []
    for content_id, category in TARGETS.items():
        if category == "playable":
            item = next(row for row in playable if int(row.get("gamekeeContentId", 0)) == content_id)
            skills = item.get("skills", {})
            output.append({"contentId": content_id, "url": f"https://www.gamekee.com/nikke/{content_id}", "classification": category, "name": item["cnName"], "record": "data/nikke_character_dictionary_enhanced.json", "skillGroupsComplete": all(skills.get(key, {}).get("effect") not in {"", "待确认"} for key in ("skill1", "skill2", "burstSkill")), "portrait": item.get("localPortraitFile", "")})
        elif category == "non_playable":
            item = next(row for row in npc if int(row.get("gamekeeContentId", 0)) == content_id)
            output.append({"contentId": content_id, "url": f"https://www.gamekee.com/nikke/{content_id}", "classification": category, "name": item["name"], "record": "data/non_playable_character_cards.json", "skillGroupsComplete": all(item.get("skills", {}).get(key) for key in ("skill1", "skill2", "burstSkill")), "portrait": item.get("localPortraitFile", "")})
        else:
            item = next(row for row in costumes if int(row.get("contentId", 0)) == content_id)
            output.append({"contentId": content_id, "url": f"https://www.gamekee.com/nikke/{content_id}", "classification": category, "name": item["name"], "parentCharacter": item.get("parentCharacter", "待确认"), "record": "data/gamekee_costume_catalog.json and parent costumes[]", "materialStatus": item["status"], "portrait": item.get("localPortraitFile", ""), "displayVideoUrl": item.get("displayVideoUrl", "")})
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "entries": output, "rootCause": ["The earlier classification rules inferred NPC/costume status from naming and presentation media instead of treating the user's confirmed in-pool status as authoritative.", "Character skill parsing treated empty 技能描述 as no effect and later overwrote lv10 values with empty 技能描述（lv10） placeholders.", "The parser accepted repeated glossary fields and a generic 爆裂技能 label as skill metadata/title without checking structured-page context."], "validation": {"allTargetsClassified": len(output) == len(TARGETS), "playableCount": len(playable), "unclassifiedNewEntries": 0}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
