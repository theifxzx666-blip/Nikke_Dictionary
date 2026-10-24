"""Build the centralized NIKKE character resource repository from verified local sources."""

import argparse
import hashlib
import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = ROOT / "cache" / "gamekee_content_details"
REPOSITORY = DATA / "character_repository"
MAPPING = DATA / "character_name_mapping.json"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
DOTGG_ROSTER = DATA / "nikke_characters.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_records(bindings: list[dict], dictionary: list[dict], profile_hashes: dict[str, str], previous: dict[str, dict] | None = None) -> list[dict]:
    by_slug = {row["url"]: row for row in dictionary}
    records = []
    for binding in bindings:
        row = by_slug[binding["dictionarySlug"]]
        content_id = str(binding["gamekeeContentId"])
        prior_assets = (previous or {}).get(binding["dictionarySlug"], {}).get("assets", {})
        assets = {
                    "repositoryRoot": f"assets/characters/{binding['dictionarySlug']}",
                    "manifest": f"assets/characters/{binding['dictionarySlug']}/manifest.json",
                    "avatar": {"url": row.get("dotggIconUrl", ""), "file": row.get("localIconFile", ""), "status": row.get("avatarStatus", "")},
                    "portrait": {"url": row.get("gamekeePortraitUrl", ""), "file": row.get("localPortraitFile", "")},
                    "costumePortrait": {"url": row.get("gamekeeCostumePortraitUrl", ""), "file": row.get("gamekeeLocalCostumePortraitFile", "")},
                    "teamCard": {"url": row.get("gamekeeTeamCardUrl", ""), "file": row.get("gamekeeLocalTeamCardFile", "")},
                    "companyIcon": {"url": row.get("gamekeeCompanyIconUrl", ""), "file": row.get("gamekeeLocalCompanyIconFile", "")},
                    "stageIcon": {"url": row.get("gamekeeStageIconUrl", ""), "file": row.get("gamekeeLocalStageIconFile", "")},
                    "weaponIcon": {"url": row.get("gamekeeWeaponIconUrl", ""), "file": row.get("gamekeeLocalWeaponIconFile", "")},
                    "rarityIcon": {"url": row.get("gamekeeRarityIconUrl", ""), "file": row.get("gamekeeLocalRarityIconFile", "")},
                    "elementIcon": {"url": row.get("gamekeeElementIconUrl", ""), "file": row.get("gamekeeLocalElementIconFile", "")},
                    "classIcon": {"url": row.get("gamekeeClassIconUrl", ""), "file": row.get("gamekeeLocalClassIconFile", "")},
                    "costumes": row.get("costumes", []),
                }
        if prior_assets.get("nikkeGgPortrait"):
            assets["nikkeGgPortrait"] = prior_assets["nikkeGgPortrait"]
        records.append(
            {
                "identity": binding,
                "core": {
                    "manufacturer": row.get("manufacturer", ""),
                    "squad": row.get("squad", ""),
                    "class": row.get("class", ""),
                    "burst": row.get("burst", ""),
                    "rarity": row.get("rarity", ""),
                    "weapon": row.get("weapon", ""),
                    "element": row.get("element", ""),
                    "burstGen": row.get("burstGen", ""),
                    "gamekeeChinese": {
                        "company": row.get("gamekeeCompanyCn", ""),
                        "squad": row.get("gamekeeSquadCn", ""),
                        "class": row.get("gamekeeClassCn", ""),
                        "burst": row.get("gamekeeStageCn", ""),
                        "weapon": row.get("gamekeeWeaponCn", ""),
                        "element": row.get("gamekeeElementCn", ""),
                    },
                },
                "combat": {
                    "skills": row.get("skills", {}),
                    "normalAttack": row.get("normalAttack", {}),
                    "favoriteItem": row.get("favoriteItem", {}),
                },
                "assets": assets,
                "availability": {"cnReleased": row.get("cnReleased", "待确认"), "basis": row.get("releaseBasis", "")},
                "guides": {"gamekeeReview": {"status": "pending_route_discovery", "sourceUrl": "", "fetchedAt": "", "contentHash": ""}},
                "sources": {
                    "gamekeeProfile": {
                        "contentId": binding["gamekeeContentId"],
                        "url": binding["evidence"]["gamekee"],
                        "payloadHash": profile_hashes[content_id],
                    }
                },
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build centralized NIKKE character resource repository")
    parser.add_argument("--apply", action="store_true", help="write the repository files")
    args = parser.parse_args()

    generated_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    mapping = read_json(MAPPING)
    bindings = mapping["bindings"]
    dictionary = read_json(DICTIONARY)
    roster = read_json(DOTGG_ROSTER)
    previous_path = REPOSITORY / "canonical" / "characters.json"
    previous = {}
    if previous_path.exists():
        try:
            previous = {item["identity"]["dictionarySlug"]: item for item in read_json(previous_path).get("characters", [])}
        except (KeyError, TypeError, json.JSONDecodeError):
            previous = {}
    content_ids = {str(item["gamekeeContentId"]) for item in bindings}
    profiles = {}
    missing_profiles = []
    profile_hashes = {}
    for content_id in sorted(content_ids, key=int):
        path = CACHE / f"content_{content_id}.json"
        if not path.is_file():
            missing_profiles.append(content_id)
            continue
        digest = sha256(path)
        profile_hashes[content_id] = digest
        profiles[content_id] = {
            "sourceUrl": f"https://www.gamekee.com/nikke/{content_id}",
            "cachedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(path.stat().st_mtime)),
            "sha256": digest,
            "payload": read_json(path),
        }

    records = build_records(bindings, dictionary, profile_hashes, previous) if not missing_profiles else []
    report = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "mappingCount": len(bindings),
        "dictionaryCount": len(dictionary),
        "nikkeGgRosterCount": len(roster),
        "gamekeeProfileCount": len(profiles),
        "missingGamekeeProfiles": missing_profiles,
        "normalizedRecordCount": len(records),
        "reviewCollection": {"status": "pending_route_discovery", "targetCharacterCount": len(bindings), "collectedCount": 0},
    }
    if args.apply:
        write_json(REPOSITORY / "sources" / "nikke_gg" / "roster.json", {"schemaVersion": 1, "sourceUrl": "https://api.dotgg.gg/nikke/characters", "snapshotAt": generated_at, "characters": roster})
        write_json(REPOSITORY / "sources" / "gamekee" / "profiles.json", {"schemaVersion": 1, "source": "GameKee character details", "snapshotAt": generated_at, "profiles": profiles})
        write_json(REPOSITORY / "sources" / "gamekee" / "reviews.json", {"schemaVersion": 1, "source": "GameKee character reviews", "status": "pending_route_discovery", "snapshotAt": generated_at, "targetCharacterCount": len(bindings), "reviews": {}})
        write_json(REPOSITORY / "canonical" / "name_mapping.json", mapping)
        write_json(REPOSITORY / "canonical" / "characters.json", {"schemaVersion": 1, "generatedAt": generated_at, "scope": "confirmed playable characters only", "characters": records})
        write_json(REPOSITORY / "state" / "collection_state.json", report["reviewCollection"] | {"lastBootstrapAt": generated_at})
        write_json(REPOSITORY / "reports" / "bootstrap_latest.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
