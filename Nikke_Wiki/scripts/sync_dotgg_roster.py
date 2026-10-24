"""Synchronize the Nikke.gg roster snapshot and aligned basic dictionary fields."""

import argparse
import hashlib
import json
import shutil
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / "cache" / "dotgg"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
ROSTER = DATA / "nikke_characters.json"
SOURCE_OVERRIDES = DATA / "character_source_overrides.json"
STATE = DATA / "character_library_state" / "dotgg_roster_state.json"
REPORTS = DATA / "character_library_reports"
BACKUPS = DATA / "character_library_backups"
API_URL = "https://api.dotgg.gg/nikke/characters"
BASIC_FIELDS = ("manufacturer", "squad", "class", "burst", "rarity", "weapon", "element", "burstGen")
ROSTER_FIELDS = ("name", "url", "img", *BASIC_FIELDS)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_roster() -> list[dict]:
    request = urllib.request.Request(API_URL, headers={"User-Agent": "Nikke-Wiki character library/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Nikke.gg roster response is not a list")

    rows = []
    for item in payload:
        row = {field: item.get(field, "") for field in ROSTER_FIELDS}
        if not row["name"] or not row["url"] or not row["img"]:
            raise ValueError(f"Nikke.gg roster entry lacks identity fields: {item!r}")
        rows.append(row)
    if len({row["url"] for row in rows}) != len(rows):
        raise ValueError("Nikke.gg roster has duplicate slugs")
    return sorted(rows, key=lambda row: row["url"])


def load_overrides() -> dict[str, str]:
    payload = json.loads(SOURCE_OVERRIDES.read_text(encoding="utf-8"))
    overrides = payload.get("dotggSlugByDictionarySlug", {})
    if not isinstance(overrides, dict):
        raise ValueError("dotggSlugByDictionarySlug must be an object")
    return overrides


def fingerprint(rows: list[dict]) -> str:
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize the Nikke.gg roster snapshot")
    parser.add_argument("--apply", action="store_true", help="write the source snapshot and aligned basic dictionary fields")
    args = parser.parse_args()

    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    source_rows = fetch_roster()
    source_by_slug = {row["url"]: row for row in source_rows}
    overrides = load_overrides()
    existing_roster = json.loads(ROSTER.read_text(encoding="utf-8")) if ROSTER.exists() else []
    existing_by_slug = {row.get("url"): row for row in existing_roster if row.get("url")}
    dictionary = json.loads(DICTIONARY.read_text(encoding="utf-8"))

    new_source = [row for row in source_rows if row["url"] not in existing_by_slug]
    changed_source = [
        {"slug": row["url"], "fields": [field for field in ROSTER_FIELDS if row.get(field) != existing_by_slug[row["url"]].get(field)]}
        for row in source_rows
        if row["url"] in existing_by_slug and row != {field: existing_by_slug[row["url"]].get(field, "") for field in ROSTER_FIELDS}
    ]

    dictionary_changes = []
    missing_dictionary = []
    for row in dictionary:
        dictionary_slug = row.get("url", "")
        source_slug = overrides.get(dictionary_slug, dictionary_slug)
        source = source_by_slug.get(source_slug)
        if not source:
            missing_dictionary.append({"name": row.get("name", ""), "slug": dictionary_slug, "dotggSlug": source_slug})
            continue
        changes = {field: {"from": row.get(field), "to": source[field]} for field in BASIC_FIELDS if row.get(field) != source[field]}
        if changes:
            dictionary_changes.append({"name": row.get("name", ""), "slug": dictionary_slug, "dotggSlug": source_slug, "fields": changes})

    dictionary_dotgg_slugs = {overrides.get(row.get("url", ""), row.get("url", "")) for row in dictionary}
    report = {
        "schemaVersion": 1,
        "source": {"provider": "Nikke.gg", "url": API_URL, "fetchedAt": fetched_at, "fingerprint": fingerprint(source_rows)},
        "mode": "apply" if args.apply else "dry-run",
        "sourceCharacterCount": len(source_rows),
        "existingSnapshotCount": len(existing_roster),
        "newSourceCharacters": new_source,
        "changedSourceCharacters": changed_source,
        "sourceCharactersMissingDictionary": [row["url"] for row in source_rows if row["url"] not in dictionary_dotgg_slugs],
        "dictionaryCharactersMissingSource": missing_dictionary,
        "dictionaryBasicFieldChanges": dictionary_changes,
    }

    if args.apply:
        backup_path = None
        if dictionary_changes:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            backup_path = BACKUPS / f"nikke_character_dictionary_enhanced_{time.strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(DICTIONARY, backup_path)
        for row in dictionary:
            source = source_by_slug.get(overrides.get(row.get("url", ""), row.get("url", "")))
            if source:
                for field in BASIC_FIELDS:
                    row[field] = source[field]
        write_json(ROSTER, source_rows)
        write_json(CACHE / "characters.json", {"source": report["source"], "characters": source_rows})
        write_json(STATE, report["source"])
        write_json(DICTIONARY, dictionary)
        report["appliedDictionaryBasicFieldChanges"] = len(dictionary_changes)
        report["dictionaryBackup"] = backup_path.as_posix() if backup_path else ""

    if args.apply:
        write_json(REPORTS / f"dotgg_roster_{time.strftime('%Y%m%d_%H%M%S')}.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
