"""Build the auditable English-Chinese character binding table."""

import argparse
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
ROSTER = DATA / "nikke_characters.json"
SOURCE_OVERRIDES = DATA / "character_source_overrides.json"
ALIAS_OVERRIDES = DATA / "character_alias_overrides.json"
OUTPUT = DATA / "character_name_mapping.json"
REPORT = DATA / "character_library_reports" / "character_name_mapping_audit.json"


def aliases(value: object) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split("|") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the NIKKE English-Chinese character binding table")
    parser.add_argument("--apply", action="store_true", help="write the mapping table and audit report")
    args = parser.parse_args()

    dictionary = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    roster = {row["url"]: row for row in json.loads(ROSTER.read_text(encoding="utf-8"))}
    overrides = json.loads(SOURCE_OVERRIDES.read_text(encoding="utf-8")).get("dotggSlugByDictionarySlug", {})
    alias_overrides = json.loads(ALIAS_OVERRIDES.read_text(encoding="utf-8")).get("overrides", {}) if ALIAS_OVERRIDES.exists() else {}
    bindings = []
    issues = []

    for row in sorted(dictionary, key=lambda item: item.get("url", "")):
        dictionary_slug = row.get("url", "")
        dotgg_slug = overrides.get(dictionary_slug, dictionary_slug)
        dotgg = roster.get(dotgg_slug)
        cn_name = row.get("gamekeeCnName") or row.get("cnName") or ""
        entry_id = row.get("gamekeeEntryId")
        content_id = row.get("gamekeeContentId")
        status = "confirmed" if dotgg and cn_name and entry_id and content_id else "needs_review"
        mapping_basis = "direct_slug" if dotgg_slug == dictionary_slug else "explicit_slug_override"
        entry = {
            "dictionarySlug": dictionary_slug,
            "dotggSlug": dotgg_slug,
            "englishName": dotgg.get("name", "") if dotgg else "",
            "chineseName": cn_name,
            "aliases": list(dict.fromkeys(aliases(row.get("aliases")) + [item["value"] for item in alias_overrides.get(dictionary_slug, [])])),
            "gamekeeEntryId": entry_id,
            "gamekeeContentId": content_id,
            "status": status,
            "mappingBasis": mapping_basis,
            "evidence": {
                "nikkeGg": f"https://nikke.gg/characters/{dotgg_slug}/" if dotgg else "",
                "gamekee": f"https://www.gamekee.com/nikke/{content_id}" if content_id else "",
            },
        }
        bindings.append(entry)
        if status != "confirmed":
            issues.append(entry)

    duplicate_fields = {}
    for field in ("dictionarySlug", "dotggSlug", "englishName", "gamekeeEntryId", "gamekeeContentId"):
        values = [item[field] for item in bindings if item[field] not in ("", None)]
        duplicate_fields[field] = sorted({value for value in values if values.count(value) > 1})
    report = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dictionaryCharacterCount": len(dictionary),
        "bindingCount": len(bindings),
        "confirmedCount": len([item for item in bindings if item["status"] == "confirmed"]),
        "needsReview": issues,
        "duplicateKeys": duplicate_fields,
    }

    if args.apply:
        OUTPUT.write_text(
            json.dumps({"schemaVersion": 1, "generatedAt": report["generatedAt"], "bindings": bindings}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
