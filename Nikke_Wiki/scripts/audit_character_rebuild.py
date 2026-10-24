"""Field-level quality audit for rebuilding the NIKKE character dictionary."""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
MAPPING = DATA / "character_name_mapping.json"
ASSET_ROOT = DATA / "character_repository" / "assets" / "characters"
PLACEHOLDERS = {"", "/", "待确认", "未确认", "unknown", "null", "None"}


def missing(value) -> bool:
    return value is None or str(value).strip() in PLACEHOLDERS


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit NIKKE character dictionary before rebuild")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))["bindings"]
    mapping_by_slug = {item["dictionarySlug"]: item for item in mapping}
    field_missing = Counter()
    placeholder_skills = []
    source_missing = []
    alias_issues = []
    asset_issues = []
    for row in rows:
        slug = row.get("url", "")
        for field in ("name", "cnName", "gamekeeEntryId", "gamekeeContentId", "manufacturer", "squad", "class", "burst", "rarity", "weapon", "element", "burstGen", "gamekeeCnName"):
            if missing(row.get(field)):
                field_missing[field] += 1
        skill_names = []
        for skill_key in ("skill1", "skill2", "burstSkill"):
            skill = row.get("skills", {}).get(skill_key, {})
            if missing(skill.get("effect")):
                skill_names.append(skill_key)
        if skill_names:
            placeholder_skills.append({"slug": slug, "name": row.get("name", ""), "skills": skill_names})
        if not row.get("source", {}).get("url") and not row.get("gamekeeContentId"):
            source_missing.append({"slug": slug, "name": row.get("name", ""), "reason": "missing GameKee source"})
        aliases = [item.strip() for item in str(row.get("aliases", "")).split("|") if item.strip()]
        if len(aliases) != len(set(aliases)):
            alias_issues.append({"slug": slug, "name": row.get("name", ""), "reason": "duplicate aliases"})
        if slug not in mapping_by_slug:
            alias_issues.append({"slug": slug, "name": row.get("name", ""), "reason": "missing identity mapping"})
        asset_dir = ASSET_ROOT / slug
        if not (asset_dir / "manifest.json").is_file():
            asset_issues.append({"slug": slug, "name": row.get("name", ""), "reason": "missing manifest"})
    report = {
        "schemaVersion": 1,
        "characterCount": len(rows),
        "mappingCount": len(mapping),
        "fieldMissingCounts": dict(sorted(field_missing.items())),
        "placeholderSkillCharacters": placeholder_skills,
        "sourceMissing": source_missing,
        "aliasIssues": alias_issues,
        "assetIssues": asset_issues,
        "riskSummary": {
            "placeholderSkillCharacterCount": len(placeholder_skills),
            "sourceMissingCount": len(source_missing),
            "aliasIssueCount": len(alias_issues),
            "assetIssueCount": len(asset_issues),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["riskSummary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
