"""Archive existing character media into one directory per character."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT / "data" / "character_repository"
ASSET_ROOT = REPOSITORY / "assets" / "characters"
DICTIONARY = ROOT / "data" / "nikke_character_dictionary_enhanced.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_file(source_value, target: Path, apply: bool) -> dict:
    source = Path(source_value) if source_value else None
    item = {"sourceFile": str(source) if source else "", "targetFile": str(target.relative_to(REPOSITORY.parent.parent)).replace("\\", "/"), "status": "missing"}
    if source and source.is_file():
        item["status"] = "available"
        item["sha256"] = digest(source)
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            item["archivedSha256"] = digest(target)
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description="Build one consolidated asset set per NIKKE character")
    parser.add_argument("--apply", action="store_true", help="copy files and update canonical records")
    args = parser.parse_args()
    source = read_json(REPOSITORY / "canonical" / "characters.json")
    records = source["characters"]
    dictionary_by_slug = {row["url"]: row for row in read_json(DICTIONARY)}
    portrait_urls = {}
    portrait_report = REPOSITORY / "reports" / "nikke_gg_portraits_latest.json"
    if portrait_report.exists():
        portrait_urls = {item.get("dictionarySlug"): item.get("url", "") for item in read_json(portrait_report).get("portraits", [])}
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    updated = []
    for record in records:
        identity = record["identity"]
        slug = identity["dictionarySlug"]
        old = record.get("assets", {})
        legacy = dictionary_by_slug.get(slug, {})
        def legacy_asset(key: str, legacy_key: str) -> dict:
            return old.get(key) or {"url": legacy.get(legacy_key.replace("File", "Url"), ""), "file": legacy.get(legacy_key, "")}
        avatar_old = legacy_asset("avatar", "localIconFile")
        team_old = legacy_asset("teamCard", "gamekeeLocalTeamCardFile")
        portrait_old = legacy_asset("portrait", "localPortraitFile")
        costume_old = legacy_asset("costumePortrait", "gamekeeLocalCostumePortraitFile")
        target_root = ASSET_ROOT / slug
        files = {
            "avatar": archive_file(avatar_old.get("file"), target_root / "avatar.png", args.apply),
            "teamCard": archive_file(team_old.get("file"), target_root / "team_card.png", args.apply),
            "portrait": archive_file(portrait_old.get("file"), target_root / "portrait.webp", args.apply),
            "costumePortrait": archive_file(costume_old.get("file"), target_root / "costume_portrait.webp", args.apply),
        }
        nikke_gg_portrait = target_root / "nikke_gg_portrait.webp"
        nikke_gg_item = {"sourceFile": "", "targetFile": f"data/character_repository/assets/characters/{slug}/nikke_gg_portrait.webp", "status": "missing"}
        if nikke_gg_portrait.is_file():
            nikke_gg_item = {"sourceFile": str(nikke_gg_portrait), "targetFile": f"data/character_repository/assets/characters/{slug}/nikke_gg_portrait.webp", "status": "available", "sha256": digest(nikke_gg_portrait), "archivedSha256": digest(nikke_gg_portrait)}
        files["nikkeGgPortrait"] = nikke_gg_item
        icon_sources = {
            "company": legacy.get("gamekeeLocalCompanyIconFile", ""),
            "stage": legacy.get("gamekeeLocalStageIconFile", ""),
            "weapon": legacy.get("gamekeeLocalWeaponIconFile", ""),
            "rarity": legacy.get("gamekeeLocalRarityIconFile", ""),
            "element": legacy.get("gamekeeLocalElementIconFile", ""),
            "class": legacy.get("gamekeeLocalClassIconFile", ""),
        }
        icons = {name: archive_file(path, target_root / "icons" / f"{name}.png", args.apply) for name, path in icon_sources.items()}
        manifest = {
            "schemaVersion": 1,
            "generatedAt": generated_at,
            "dictionarySlug": slug,
            "nameCn": identity["chineseName"],
            "nameEn": identity["englishName"],
            "gamekeeContentId": identity["gamekeeContentId"],
            "nikkeGgSlug": identity["dotggSlug"],
            "files": files,
            "icons": icons,
        }
        if args.apply:
            (target_root / "manifest.json").parent.mkdir(parents=True, exist_ok=True)
            (target_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            record["assets"] = {
                "repositoryRoot": f"assets/characters/{slug}",
                "manifest": f"assets/characters/{slug}/manifest.json",
                "avatar": {"url": avatar_old.get("url", "") or legacy.get("dotggIconUrl", ""), "file": f"assets/characters/{slug}/avatar.png", "status": files["avatar"]["status"]},
                "teamCard": {"url": team_old.get("url", "") or legacy.get("gamekeeTeamCardUrl", ""), "file": f"assets/characters/{slug}/team_card.png", "status": files["teamCard"]["status"]},
                "portrait": {"url": portrait_old.get("url", "") or legacy.get("gamekeePortraitUrl", ""), "file": f"assets/characters/{slug}/portrait.webp", "status": files["portrait"]["status"]},
                "costumePortrait": {"url": costume_old.get("url", "") or legacy.get("gamekeeCostumePortraitUrl", ""), "file": f"assets/characters/{slug}/costume_portrait.webp", "status": files["costumePortrait"]["status"]},
                "nikkeGgPortrait": {"url": portrait_urls.get(slug, ""), "file": f"assets/characters/{slug}/nikke_gg_portrait.webp", "status": files["nikkeGgPortrait"]["status"]},
                "icons": {name: {"file": f"assets/characters/{slug}/icons/{name}.png", "status": item["status"]} for name, item in icons.items()},
                "costumes": old.get("costumes", []),
            }
        updated.append(manifest)
    if args.apply:
        source["generatedAt"] = generated_at
        (REPOSITORY / "canonical" / "characters.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report_path = REPOSITORY / "reports" / "asset_repository_latest.json"
    else:
        report_path = REPOSITORY / "reports" / "asset_repository_dry_run.json"
    report = {"generatedAt": generated_at, "apply": args.apply, "characterCount": len(updated), "availableSets": sum(all(item["status"] == "available" for item in [*m["files"].values(), *m["icons"].values()]) for m in updated), "manifests": updated}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"apply": args.apply, "characterCount": len(updated), "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
