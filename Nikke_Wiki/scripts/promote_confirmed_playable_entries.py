from __future__ import annotations

import json
import time
from pathlib import Path

from refresh_character_cards import ASSET_DIR, DICTIONARY, apply_gamekee_canonical_fields, download, first_value, normalize_url, parse_payload, records, skill_summary, suffix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DETAIL_DIR = PROJECT_ROOT / "cache" / "gamekee_content_details"
NPC_CARDS = PROJECT_ROOT / "data" / "non_playable_character_cards.json"
COSTUME_CATALOG = PROJECT_ROOT / "data" / "gamekee_costume_catalog.json"
REPORT = PROJECT_ROOT / "data" / "reports" / "confirmed_playable_entry_promotion_report.json"
PROCESSED_INDEX = PROJECT_ROOT / "data" / "character_library_state" / "processed_versions.json"
CN_RELEASE_STATUS = PROJECT_ROOT / "data" / "cn_release_status.json"
TARGETS = {
    708686: {"entryId": 217280, "cnName": "方舟黑色游侠", "aliases": ["方舟游侠"], "url": "gamekee-708686"},
    711133: {"entryId": 218253, "cnName": "灰姑娘：琉璃波光", "aliases": [], "url": "gamekee-711133"},
    711739: {"entryId": 218512, "cnName": "玛律恰那：海洋进修", "aliases": [], "url": "gamekee-711739"},
    713891: {"entryId": 219258, "cnName": "拉普拉斯：究极英雄", "aliases": [], "url": "gamekee-713891"},
    713899: {"entryId": 219257, "cnName": "麦斯威尔：平凡技师", "aliases": [], "url": "gamekee-713899"},
}
FIELDS = {"\u4f01\u4e1a": "gamekeeCompanyCn", "\u90e8\u961f": "gamekeeSquadCn", "\u9636\u6bb5": "gamekeeStageCn", "\u5c5e\u6027": "gamekeeElementCn", "\u804c\u4e1a": "gamekeeClassCn", "\u6b66\u5668": "gamekeeWeaponCn", "\u6b66\u5668\uff08\u540d\uff09": "weaponNameCn", "\u7a00\u6709\u5ea6": "rarity", "\u7b80\u4ecb": "description"}
CARD_LABEL = "\u90e8\u961f\u6210\u54581"
DISPLAY_LABEL = "\u89d2\u8272\u5c55\u793a"


def display_video(content: dict) -> str:
    for row in content.get("baseData", []):
        texts = [cell.get("value", "") for cell in row if cell.get("type") == "text"]
        if not texts or texts[0] != DISPLAY_LABEL:
            continue
        for cell in row:
            if cell.get("type") == "video" and isinstance(cell.get("value"), str):
                return cell["value"] if cell["value"].startswith("https:") else "https:" + cell["value"]
    return ""


def static_display_image(items: list[tuple[str, list[str], list[str]]]) -> str:
    return next((images[0] for label, _, images in items if label == DISPLAY_LABEL and images), "")


def main() -> None:
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    existing = {int(row.get("gamekeeContentId", 0)): row for row in rows}
    tree = json.loads((PROJECT_ROOT / "data" / "gamekee_api_tree_64581.json").read_text(encoding="utf-8"))
    tree_entries = {int(entry["content_id"]): entry for entry in __import__("refresh_character_cards").flatten_tree(tree.get("data") or []) if entry.get("content_id")}
    promoted, failures = [], []
    for content_id, meta in TARGETS.items():
        try:
            payload = json.loads((DETAIL_DIR / f"content_{content_id}.json").read_text(encoding="utf-8"))
            content = parse_payload(payload)
            if not content:
                raise ValueError("unparseable cached content")
            items = records(content)
            values = {label: first_value(cell_values) for label, cell_values, _ in items}
            card_url = next((images[0] for label, _, images in items if label == CARD_LABEL and images), "")
            display_url = static_display_image(items)
            team_card_url = normalize_url(tree_entries.get(content_id, {}).get("icon", "") or card_url)
            local_icon_file = ""
            if team_card_url:
                icon_output = PROJECT_ROOT / "assets" / "nikke_character_icons" / f"gamekee_{content_id}{suffix(team_card_url)}"
                ok, result = download(team_card_url, icon_output)
                if not ok:
                    raise ValueError(result)
                local_icon_file = icon_output.as_posix()
            portrait_file = ""
            if display_url:
                portrait_output = ASSET_DIR / "portraits" / f"gamekee_{content_id}{suffix(display_url)}"
                ok, result = download(display_url, portrait_output)
                if not ok:
                    raise ValueError(result)
                portrait_file = portrait_output.as_posix()
            team_card_file = ""
            if card_url:
                output = ASSET_DIR / "playable_form_cards" / f"{content_id}{suffix(card_url)}"
                ok, result = download(card_url, output)
                if not ok:
                    raise ValueError(result)
                team_card_file = output.as_posix()
            row = existing.get(content_id, {})
            row.update({
                "name": meta["cnName"], "cnName": meta["cnName"], "aliases": meta["aliases"], "url": meta["url"],
                "characterCategory": "playable", "englishNameStatus": "待确认", "gamekeeEntryId": meta["entryId"], "gamekeeContentId": content_id,
                "gamekeeCnName": values.get("角色名称", meta["cnName"]), "skills": skill_summary(items)[0], "normalAttack": skill_summary(items)[1],
                "source": {"provider": "GameKee", "contentId": content_id, "url": f"https://www.gamekee.com/nikke/{content_id}"},
                "gamekeeIconUrl": team_card_url, "localIconFile": local_icon_file,
                "gamekeeTeamCardUrl": card_url, "gamekeeLocalTeamCardFile": team_card_file,
                "gamekeePortraitUrl": display_url, "gamekeeDisplayVideoUrl": display_video(content), "localPortraitFile": portrait_file,
            })
            row.update({field: values.get(label, "待确认") or "待确认" for label, field in FIELDS.items()})
            apply_gamekee_canonical_fields(row)
            if content_id in existing:
                rows[rows.index(existing[content_id])] = row
            else:
                rows.append(row)
            promoted.append({"contentId": content_id, "name": meta["cnName"], "avatar": local_icon_file, "portrait": portrait_file, "display": display_url or row["gamekeeDisplayVideoUrl"]})
        except Exception as exc:
            failures.append({"contentId": content_id, "error": str(exc)})
    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    release_status = json.loads(CN_RELEASE_STATUS.read_text(encoding="utf-8"))
    for meta in TARGETS.values():
        release_status[meta["cnName"]] = {
            "status": "已上线",
            "date": "",
            "basis": "用户确认：已加入国服卡池",
            "note": "独立可操作角色，不归类为NPC或本体皮肤。",
        }
    CN_RELEASE_STATUS.write_text(json.dumps(release_status, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot_path = PROJECT_ROOT / "data" / "character_library_state" / "online_index_snapshot.json"
    if snapshot_path.exists():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        processed = json.loads(PROCESSED_INDEX.read_text(encoding="utf-8")) if PROCESSED_INDEX.exists() else {}
        for entry_id, item in snapshot.get("entries", {}).items():
            if int(item.get("contentId", 0)) in TARGETS:
                processed[entry_id] = {"version": item["version"], "contentId": item["contentId"], "processedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        PROCESSED_INDEX.write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")

    npc = json.loads(NPC_CARDS.read_text(encoding="utf-8"))
    NPC_CARDS.write_text(json.dumps([row for row in npc if int(row.get("gamekeeContentId", 0)) != 708686], ensure_ascii=False, indent=2), encoding="utf-8")
    catalog = json.loads(COSTUME_CATALOG.read_text(encoding="utf-8"))
    COSTUME_CATALOG.write_text(json.dumps([row for row in catalog if int(row.get("contentId", 0)) not in {711133, 711739, 713891, 713899}], ensure_ascii=False, indent=2), encoding="utf-8")
    for row in rows:
        row["costumes"] = [costume for costume in row.get("costumes", []) if int(costume.get("contentId", 0)) not in {711133, 711739, 713891, 713899}]
    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "promoted": promoted, "failures": failures, "playableCount": len(rows)}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
