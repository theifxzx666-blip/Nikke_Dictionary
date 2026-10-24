"""Export normalized character records as an Obsidian-ready Markdown database."""

import argparse
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT / "data" / "character_repository"
DEFAULT_OUTPUT = ROOT / "obsidian_character_database" / "NIKKE角色库"


def scalar(value) -> str:
    return '"' + str(value or "").replace('"', '\\"') + '"'


def asset_path(record: dict, key: str) -> str:
    assets = record.get("assets", {})
    if key in {"avatar", "teamCard", "portrait", "costumePortrait", "nikkeGgPortrait"}:
        item = assets.get(key, {})
    else:
        item = assets.get("icons", {}).get(key, {})
    return item.get("file", "") if item.get("status") == "available" else ""


def note(record: dict) -> str:
    identity = record["identity"]
    core = record["core"]
    chinese = core["gamekeeChinese"]
    aliases = ", ".join(scalar(item) for item in identity["aliases"])
    avatar = asset_path(record, "avatar")
    team_card = asset_path(record, "teamCard")
    portrait = asset_path(record, "portrait")
    nikke_gg_portrait = asset_path(record, "nikkeGgPortrait")
    costume = asset_path(record, "costumePortrait")
    icons = {key: asset_path(record, key) for key in ("company", "stage", "weapon", "rarity", "element", "class")}
    image_lines = "\n".join(f"- {key}: ![[{value}]]" if value else f"- {key}: 待补充" for key, value in {"avatar": avatar, "team_card": team_card, "nikke_gg_portrait": nikke_gg_portrait, "gamekee_portrait": portrait, "costume_portrait": costume, **{f"icon_{k}": v for k, v in icons.items()}}.items())
    return f'''---
type: nikke_character
id: {scalar(identity["dictionarySlug"])}
name_cn: {scalar(identity["chineseName"])}
name_en: {scalar(identity["englishName"])}
aliases: [{aliases}]
binding_status: {identity["status"]}
dotgg_slug: {scalar(identity["dotggSlug"])}
gamekee_entry_id: {identity["gamekeeEntryId"]}
gamekee_content_id: {identity["gamekeeContentId"]}
nikke_gg_url: {scalar(identity["evidence"]["nikkeGg"])}
gamekee_url: {scalar(identity["evidence"]["gamekee"])}
manufacturer: {scalar(core["manufacturer"])}
squad: {scalar(core["squad"])}
class: {scalar(core["class"])}
burst: {scalar(core["burst"])}
weapon: {scalar(core["weapon"])}
element: {scalar(core["element"])}
rarity: {scalar(core["rarity"])}
cn_release_status: {scalar(record["availability"]["cnReleased"])}
gamekee_review_status: {record["guides"]["gamekeeReview"]["status"]}
source_snapshot: {scalar(record["sources"]["gamekeeProfile"]["payloadHash"])}
asset_manifest: {scalar(assets_path(record))}
avatar_file: {scalar(avatar)}
team_card_file: {scalar(team_card)}
portrait_file: {scalar(portrait)}
nikke_gg_portrait_file: {scalar(nikke_gg_portrait)}
costume_portrait_file: {scalar(costume)}
asset_status: {scalar(asset_status(record))}
---

# {identity["chineseName"]} / {identity["englishName"]}

## 角色素材

{image_lines}

## 基础资料

- 中文企业：{chinese["company"]}
- 中文部队：{chinese["squad"]}
- 中文职业：{chinese["class"]}
- 中文爆裂：{chinese["burst"]}
- 中文武器：{chinese["weapon"]}
- 中文属性：{chinese["element"]}

## 技能与普通攻击

```json
{json.dumps(record["combat"], ensure_ascii=False, indent=2)}
```

## GameKee 评测攻略

当前状态：`{record["guides"]["gamekeeReview"]["status"]}`

## 来源

- [Nikke.gg]({identity["evidence"]["nikkeGg"]})
- [GameKee]({identity["evidence"]["gamekee"]})
'''


def assets_path(record: dict) -> str:
    return record.get("assets", {}).get("manifest", "")


def asset_status(record: dict) -> str:
    assets = record.get("assets", {})
    statuses = []
    for key in ("avatar", "teamCard", "portrait", "nikkeGgPortrait", "costumePortrait"):
        statuses.append(assets.get(key, {}).get("status", "missing"))
    statuses.extend(item.get("status", "missing") for item in assets.get("icons", {}).values())
    return "complete" if statuses and all(value == "available" for value in statuses) else "partial"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export NIKKE characters into an Obsidian database directory")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="target Obsidian database directory")
    args = parser.parse_args()

    source = json.loads((REPOSITORY / "canonical" / "characters.json").read_text(encoding="utf-8"))
    characters = source["characters"]
    notes_dir = args.output / "Characters"
    notes_dir.mkdir(parents=True, exist_ok=True)
    templates_dir = args.output / "Templates"
    views_dir = args.output / "Views"
    templates_dir.mkdir(parents=True, exist_ok=True)
    views_dir.mkdir(parents=True, exist_ok=True)
    source_assets = ROOT / "data" / "character_repository" / "assets" / "characters"
    vault_assets = args.output / "assets" / "characters"
    if source_assets.is_dir():
        for source_file in source_assets.rglob("*"):
            if source_file.is_file():
                target_file = vault_assets / source_file.relative_to(source_assets)
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, target_file)
    (templates_dir / "角色档案.md").write_text((ROOT / "obsidian_character_database" / "Templates" / "角色档案.md").read_text(encoding="utf-8"), encoding="utf-8")
    (views_dir / "角色核对.md").write_text((ROOT / "obsidian_character_database" / "Views" / "角色核对.md").read_text(encoding="utf-8"), encoding="utf-8")
    for record in characters:
        slug = record["identity"]["dictionarySlug"]
        (notes_dir / f"{slug}.md").write_text(note(record), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "characterNotes": len(characters), "template": True, "view": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
