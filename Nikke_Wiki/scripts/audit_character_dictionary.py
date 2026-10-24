"""Audit the character dictionary without fetching or changing source data."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
ROSTER = DATA / "nikke_characters.json"
SOURCE_OVERRIDES = DATA / "character_source_overrides.json"
BASIC_FIELDS = ("manufacturer", "squad", "class", "burst", "rarity", "weapon", "element", "burstGen")
GAMEKEE_REQUIRED = ("gamekeeCompanyCn", "gamekeeSquadCn", "gamekeeStageCn", "gamekeeElementCn", "gamekeeWeaponCn")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit NIKKE character dictionary coverage and identity")
    parser.add_argument("--output", type=Path, help="optional JSON report output path")
    args = parser.parse_args()

    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    overrides = json.loads(SOURCE_OVERRIDES.read_text(encoding="utf-8")).get("dotggSlugByDictionarySlug", {})
    roster_by_slug = {row["url"]: row for row in roster}
    names = [row.get("name", "") for row in rows]
    slugs = [row.get("url", "") for row in rows]

    duplicate_names = sorted({name for name in names if name and names.count(name) > 1})
    duplicate_slugs = sorted({slug for slug in slugs if slug and slugs.count(slug) > 1})
    duplicate_gamekee_ids = sorted({
        content_id for content_id in (row.get("gamekeeContentId") for row in rows)
        if content_id and sum(other.get("gamekeeContentId") == content_id for other in rows) > 1
    })
    basic_conflicts = []
    for row in rows:
        dictionary_slug = row.get("url", "")
        source_slug = overrides.get(dictionary_slug, dictionary_slug)
        source = roster_by_slug.get(source_slug)
        if not source:
            continue
        fields = {field: {"dictionary": row.get(field), "nikkeGg": source.get(field)} for field in BASIC_FIELDS if row.get(field) != source.get(field)}
        if fields:
            basic_conflicts.append({"name": row.get("name", ""), "slug": dictionary_slug, "dotggSlug": source_slug, "fields": fields})

    dictionary_dotgg_slugs = {overrides.get(slug, slug) for slug in slugs}

    report = {
        "dictionaryCharacters": len(rows),
        "nikkeGgSnapshotCharacters": len(roster),
        "duplicateNames": duplicate_names,
        "duplicateSlugs": duplicate_slugs,
        "duplicateGameKeeContentIds": duplicate_gamekee_ids,
        "nikkeGgCharactersMissingDictionary": sorted(set(roster_by_slug) - dictionary_dotgg_slugs),
        "dictionaryCharactersMissingNikkeGg": sorted(dictionary_slug for dictionary_slug in slugs if overrides.get(dictionary_slug, dictionary_slug) not in roster_by_slug),
        "basicFieldConflicts": basic_conflicts,
        "missingGameKeeRequiredFields": [row.get("name", "") for row in rows if any(not row.get(field) for field in GAMEKEE_REQUIRED)],
        "missingCoreSkills": [row.get("name", "") for row in rows if not all(row.get("skills", {}).get(field, {}).get("effect") for field in ("skill1", "skill2", "burstSkill"))],
        "missingLocalPortraits": [row.get("name", "") for row in rows if not row.get("localPortraitFile") or not Path(row["localPortraitFile"]).is_file()],
        "avatarPendingConfirmation": [
            row.get("name", "") for row in rows if row.get("avatarStatus") not in {"available", "available_derived"}
        ],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
