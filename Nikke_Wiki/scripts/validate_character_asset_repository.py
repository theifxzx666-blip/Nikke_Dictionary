"""Validate the per-character asset archive and canonical relative paths."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT / "data" / "character_repository"
ASSET_ROOT = REPOSITORY / "assets" / "characters"


def main() -> None:
    records = json.loads((REPOSITORY / "canonical" / "characters.json").read_text(encoding="utf-8"))["characters"]
    errors = []
    missing = []
    for record in records:
        slug = record["identity"]["dictionarySlug"]
        root = ASSET_ROOT / slug
        manifest = root / "manifest.json"
        if not manifest.is_file():
            errors.append(f"{slug}: missing manifest.json")
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for group, items in (("files", data.get("files", {})), ("icons", data.get("icons", {}))):
            for name, item in items.items():
                if item.get("status") == "available":
                    target = ROOT / item["targetFile"]
                    if not target.is_file():
                        errors.append(f"{slug}: archived file missing {group}.{name}")
                else:
                    missing.append({"slug": slug, "asset": f"{group}.{name}"})
        assets = record.get("assets", {})
        nikke_portrait = assets.get("nikkeGgPortrait", {})
        if nikke_portrait.get("status") == "available" and not (REPOSITORY / nikke_portrait.get("file", "")).is_file():
            errors.append(f"{slug}: Nikke.gg portrait file missing")
        for value in [assets.get("repositoryRoot", ""), assets.get("manifest", "")]:
            if value and Path(value).is_absolute():
                errors.append(f"{slug}: absolute canonical asset path {value}")
    report = {"characterCount": len(records), "directoryCount": len([p for p in ASSET_ROOT.iterdir() if p.is_dir()]) if ASSET_ROOT.is_dir() else 0, "missing": missing, "errors": errors, "passed": not errors and len(records) == len([p for p in ASSET_ROOT.iterdir() if p.is_dir()])}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
