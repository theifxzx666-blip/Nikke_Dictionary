"""Validate cross-file consistency of the centralized character resource repository."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT / "data" / "character_repository"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate NIKKE character resource repository")
    parser.add_argument("--output", type=Path, help="optional JSON validation report path")
    args = parser.parse_args()

    roster = read_json(REPOSITORY / "sources" / "nikke_gg" / "roster.json")["characters"]
    profiles = read_json(REPOSITORY / "sources" / "gamekee" / "profiles.json")["profiles"]
    reviews = read_json(REPOSITORY / "sources" / "gamekee" / "reviews.json")
    bindings = read_json(REPOSITORY / "canonical" / "name_mapping.json")["bindings"]
    characters = read_json(REPOSITORY / "canonical" / "characters.json")["characters"]

    binding_slugs = [row["dictionarySlug"] for row in bindings]
    dotgg_slugs = [row["dotggSlug"] for row in bindings]
    entry_ids = [row["gamekeeEntryId"] for row in bindings]
    content_ids = [str(row["gamekeeContentId"]) for row in bindings]
    character_slugs = [row["identity"]["dictionarySlug"] for row in characters]
    errors = {
        "duplicateDictionarySlugs": sorted({value for value in binding_slugs if binding_slugs.count(value) > 1}),
        "duplicateDotggSlugs": sorted({value for value in dotgg_slugs if dotgg_slugs.count(value) > 1}),
        "duplicateGameKeeEntryIds": sorted({value for value in entry_ids if entry_ids.count(value) > 1}),
        "duplicateGameKeeContentIds": sorted({value for value in content_ids if content_ids.count(value) > 1}),
        "missingProfiles": sorted(set(content_ids) - set(profiles)),
        "unexpectedProfiles": sorted(set(profiles) - set(content_ids)),
        "missingCanonicalRecords": sorted(set(binding_slugs) - set(character_slugs)),
        "unexpectedCanonicalRecords": sorted(set(character_slugs) - set(binding_slugs)),
        "missingNikkeGgSlugs": sorted(set(dotgg_slugs) - {row["url"] for row in roster}),
        "invalidReviewStatus": reviews.get("status") not in {"pending_route_discovery", "available", "partial", "failed"},
        "reviewTargetCountMismatch": reviews.get("targetCharacterCount") != len(bindings),
    }
    report = {
        "mappingCount": len(bindings),
        "canonicalCharacterCount": len(characters),
        "nikkeGgRosterCount": len(roster),
        "gamekeeProfileCount": len(profiles),
        "gamekeeReviewStatus": reviews.get("status"),
        "errors": errors,
        "passed": not any(bool(value) for value in errors.values()),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
