"""Apply user-confirmed aliases without changing character identity keys."""

import argparse
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
OVERRIDES = DATA / "character_alias_overrides.json"
REPORT = DATA / "character_library_reports" / "alias_override_latest.json"
MAPPING = DATA / "character_name_mapping.json"
CANONICAL = DATA / "character_repository" / "canonical" / "characters.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply explicit character alias overrides")
    parser.add_argument("--apply", action="store_true", help="write dictionary changes")
    args = parser.parse_args()
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))["overrides"]
    changes = []
    for row in rows:
        slug = row.get("url", "")
        entries = overrides.get(slug, [])
        if not entries:
            continue
        existing = [item.strip() for item in str(row.get("aliases", "")).split("|") if item.strip()]
        added = []
        for entry in entries:
            value = entry["value"]
            if value not in existing:
                existing.append(value)
                added.append(value)
        if added:
            changes.append({"dictionarySlug": slug, "name": row.get("name", ""), "added": added})
            if args.apply:
                row["aliases"] = "|".join(existing)
                details = row.setdefault("aliasDetails", [])
                known = {item.get("value") for item in details}
                details.extend(entry for entry in entries if entry["value"] not in known)
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "apply": args.apply, "overrideCount": sum(len(v) for v in overrides.values()), "changedCharacters": changes}
    if args.apply and changes:
        backup = DATA / "character_library_backups" / f"nikke_character_dictionary_enhanced_{time.strftime('%Y%m%d_%H%M%S')}_before_alias_override.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DICTIONARY, backup)
        DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed = {item["dictionarySlug"] for item in changes}
        if MAPPING.exists():
            mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
            for binding in mapping.get("bindings", []):
                if binding.get("dictionarySlug") in changed:
                    row = next(item for item in rows if item.get("url") == binding["dictionarySlug"])
                    binding["aliases"] = [item.strip() for item in str(row.get("aliases", "")).split("|") if item.strip()]
            MAPPING.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if CANONICAL.exists():
            canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
            for record in canonical.get("characters", []):
                if record.get("identity", {}).get("dictionarySlug") in changed:
                    row = next(item for item in rows if item.get("url") == record["identity"]["dictionarySlug"])
                    record["identity"]["aliases"] = [item.strip() for item in str(row.get("aliases", "")).split("|") if item.strip()]
            CANONICAL.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["backup"] = str(backup)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
