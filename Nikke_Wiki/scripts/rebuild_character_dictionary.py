"""Create an auditable rebuilt dictionary without overwriting the existing one."""

import argparse
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "nikke_character_dictionary_enhanced.json"
MAPPING = DATA / "character_name_mapping.json"
OUT = DATA / "character_repository" / "canonical" / "characters_rebuilt.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a rebuilt NIKKE dictionary snapshot")
    parser.add_argument("--apply", action="store_true", help="write rebuilt canonical JSON")
    args = parser.parse_args()
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    mapping_by_slug = {item["dictionarySlug"]: item for item in mapping["bindings"]}
    characters = []
    for row in rows:
        slug = row.get("url", "")
        binding = mapping_by_slug.get(slug)
        if not binding or binding.get("status") != "confirmed":
            continue
        item = dict(row)
        item["identityVerification"] = {"status": binding.get("status", "needs_review"), "nikkeGgSlug": binding.get("dotggSlug", ""), "gamekeeEntryId": binding.get("gamekeeEntryId"), "gamekeeContentId": binding.get("gamekeeContentId")}
        item["qualityFlags"] = {
            "placeholderSkills": [key for key in ("skill1", "skill2", "burstSkill") if str(item.get("skills", {}).get(key, {}).get("effect", "")).strip() in {"", "待确认"}],
            "missingGameKeeName": not item.get("gamekeeCnName"),
        }
        characters.append(item)
    result = {
        "schemaVersion": 1,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "rebuildBasis": "Existing verified snapshots re-audited; unresolved values remain explicitly marked.",
        "sourceDictionary": str(SOURCE),
        "characters": characters,
    }
    report = {"characterCount": len(characters), "excludedUnconfirmed": len(rows) - len(characters), "apply": args.apply}
    if args.apply:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "output": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
