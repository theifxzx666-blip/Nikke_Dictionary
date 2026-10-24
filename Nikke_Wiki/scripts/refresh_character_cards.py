from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"
ASSET_DIR = PROJECT_ROOT / "assets" / "gamekee_character_assets"
DICTIONARY = DATA_DIR / "nikke_character_dictionary_enhanced.json"
TREE_CACHE = DATA_DIR / "gamekee_api_tree_64581.json"
FILTER_CACHE = DATA_DIR / "gamekee_entry_filter_64599.json"
SKIN_CATALOG = DATA_DIR / "gamekee_costume_catalog.json"
REPORT = DATA_DIR / "reports" / "character_card_refresh_report.json"
DETAIL_DIR = CACHE_DIR / "gamekee_content_details"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "X-Requested-With": "XMLHttpRequest",
    "game-alias": "nikke",
    "Lang": "zh-cn",
    "device-num": "1",
    "Referer": "https://www.gamekee.com/nikke/second/64581",
}

PROFILE_LABELS = {
    "企业": "gamekeeCompanyCn",
    "部队": "gamekeeSquadCn",
    "阶段": "gamekeeStageCn",
    "属性": "gamekeeElementCn",
    "职业": "gamekeeClassCn",
    "武器": "gamekeeWeaponCn",
    "武器（名）": "weaponNameCn",
}
NORMAL_ATTACK_LABELS = {
    "武器": "type",
    "武器（名）": "name",
    "操作类型": "operationType",
    "最大装弹数": "ammo",
    "换弹时间": "reloadTime",
    "最佳攻击范围": "optimalRange",
    "武器伤害": "damage",
}
SKILL_PREFIXES = {
    "技能1名称": "skill1",
    "技能2名称": "skill2",
    "爆裂技能名称": "burstSkill",
    "爆裂技能": "burstSkill",
}
SKILL_COOLDOWN_LABEL = "\u51b7\u5374\u65f6\u95f4"
SKILL_TYPE_LABEL = "\u6280\u80fd\u7c7b\u578b"
SKILL_DESCRIPTION_LABEL = "\u6280\u80fd\u63cf\u8ff0"
PENDING = "\u5f85\u786e\u8ba4"
NORMAL_WEAPON_TYPE_LABEL = "\u6b66\u5668\u7c7b\u578b"
NORMAL_WEAPON_NAME_LABEL = "\u6b66\u5668\u540d\u79f0"
NORMAL_AMMO_LABEL = "\u6700\u5927\u88c5\u5f39\u6570"
NORMAL_RELOAD_LABEL = "\u6362\u5f39\u65f6\u95f4"
NORMAL_DESCRIPTION_LABEL = "\u666e\u653b\u63cf\u8ff0"
CANONICAL_COMPANY = {"\u6781\u4e50\u51c0\u571f": "Elysion", "\u7c73\u897f\u5229\u65af": "Missilis", "\u6cf0\u7279\u62c9": "Tetra", "\u671d\u5723\u8005": "Pilgrim", "\u53cd\u5e38\u8005": "Abnormal", "\u53cd\u5e38": "Abnormal"}
CANONICAL_CLASS = {"\u706b\u529b\u578b": "Attacker", "\u9632\u5fa1\u578b": "Defender", "\u8f85\u52a9\u578b": "Supporter"}
CANONICAL_WEAPON = {"\u6b65\u67aa": "AR", "\u673a\u67aa": "MG", "\u51b2\u950b\u67aa": "SMG", "\u9710\u5f39\u67aa": "SG", "\u9730\u5f39\u67aa": "SG", "\u72d9\u51fb\u6b65\u67aa": "SR", "\u53d1\u5c04\u5668": "RL"}
CANONICAL_ELEMENT = {"\u71c3\u70e7": "Fire", "\u6c34\u51b7": "Water", "\u98ce\u538b": "Wind", "\u7535\u51fb": "Electric", "\u94c1\u7532": "Iron"}
CANONICAL_BURST = {"\u4e00\u9636": "1", "\u4e8c\u9636": "2", "\u4e09\u9636": "3"}


def request(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()


def request_json(url: str) -> dict:
    return json.loads(request(url).decode("utf-8-sig"))


def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


def content_url(url: str) -> str:
    return normalize_url(url).replace("https://api-cdn.gamekee.com/", "https://cdnimg-v2.gamekee.com/")


def flatten_tree(nodes: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for node in nodes:
        flat.append(node)
        flat.extend(flatten_tree(node.get("child") or []))
    return flat


def cache_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def text_values(row: list[dict]) -> list[str]:
    values: list[str] = []
    for cell in row:
        value = cell.get("value")
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return values


def records(content: dict) -> list[tuple[str, list[str], list[str]]]:
    result = []
    for row in content.get("baseData", []):
        values = text_values(row)
        if not values:
            continue
        images = [normalize_url(cell.get("value", "")) for cell in row if cell.get("type") == "image" and isinstance(cell.get("value"), str)]
        result.append((values[0], values[1:], images))
    return result


def first_value(values: list[str]) -> str:
    return values[0] if values else ""


def apply_gamekee_canonical_fields(row: dict) -> None:
    """Keep dictionary fields and GameKee Chinese fields in sync for exports."""
    row["manufacturer"] = CANONICAL_COMPANY.get(row.get("gamekeeCompanyCn", ""), row.get("manufacturer", ""))
    row["squad"] = row.get("gamekeeSquadCn", "") or row.get("squad", "")
    row["class"] = CANONICAL_CLASS.get(row.get("gamekeeClassCn", ""), row.get("class", ""))
    row["burst"] = CANONICAL_BURST.get(row.get("gamekeeStageCn", ""), row.get("burst", ""))
    row["weapon"] = CANONICAL_WEAPON.get(row.get("gamekeeWeaponCn", ""), row.get("weapon", ""))
    row["element"] = CANONICAL_ELEMENT.get(row.get("gamekeeElementCn", ""), row.get("element", ""))


def skill_summary(items: list[tuple[str, list[str], list[str]]]) -> tuple[dict, dict]:
    skills: dict[str, dict] = {}
    normal_attack: dict[str, str] = {}
    active: dict | None = None
    awaiting_description = False
    effect_captured = False
    for index, (label, values, _) in enumerate(items):
        prefix = SKILL_PREFIXES.get(label)
        # "爆裂技能" is also used in glossary text. It is a skill title only
        # when followed by its icon row in GameKee's structured page layout.
        if label == "爆裂技能" and (index + 1 >= len(items) or items[index + 1][0] != "爆裂技能图标"):
            prefix = None
        if prefix:
            active = {"name": first_value(values), "type": "待确认", "cooldown": "待确认", "effect": "待确认"}
            skills[prefix] = active
            awaiting_description = False
            effect_captured = False
            continue
        if label in NORMAL_ATTACK_LABELS:
            normal_attack[NORMAL_ATTACK_LABELS[label]] = first_value(values)
        # Newer GameKee pages put normal-attack data in a compact row where
        # ammo, the reload label, and reload time share the same value list.
        if label == NORMAL_WEAPON_TYPE_LABEL:
            normal_attack["type"] = first_value(values)
        elif label == NORMAL_WEAPON_NAME_LABEL:
            normal_attack["name"] = first_value(values)
        elif label == NORMAL_AMMO_LABEL:
            normal_attack["ammo"] = first_value(values)
            if NORMAL_RELOAD_LABEL in values:
                reload_index = values.index(NORMAL_RELOAD_LABEL) + 1
                if reload_index < len(values):
                    normal_attack["reloadTime"] = values[reload_index]
        elif label == NORMAL_RELOAD_LABEL:
            normal_attack["reloadTime"] = first_value(values)
        elif label == NORMAL_DESCRIPTION_LABEL:
            normal_attack["effect"] = first_value(values)
        if not active:
            continue
        # Use escaped labels so this parser remains stable under Windows code pages.
        if label == SKILL_COOLDOWN_LABEL and not effect_captured:
            active["cooldown"] = first_value(values) or PENDING
            continue
        if label == SKILL_TYPE_LABEL and not effect_captured:
            active["type"] = first_value(values) or PENDING
            continue
        if label == SKILL_DESCRIPTION_LABEL:
            awaiting_description = True
            if first_value(values):
                active["effect"] = first_value(values)
            continue
        if label == "lv10" and awaiting_description:
            active["effect"] = first_value(values) or PENDING
            awaiting_description = False
            effect_captured = True
            continue
        # Glossary blocks below a skill can repeat labels such as "冷却时间".
        # Metadata is only valid before this skill's level-10 effect is captured.
        if label == "冷却时间" and not effect_captured:
            active["cooldown"] = first_value(values) or "待确认"
        elif label == "技能类型" and not effect_captured:
            active["type"] = first_value(values) or "待确认"
        elif label in {"技能描述（lv10)", "技能描述（lv10)）"} and not effect_captured:
            active["effect"] = first_value(values) or "待确认"
            awaiting_description = False
        elif label == "技能描述":
            awaiting_description = True
            if first_value(values):
                active["effect"] = first_value(values)
        elif label == "lv10" and awaiting_description:
            active["effect"] = first_value(values) or "待确认"
            awaiting_description = False
            effect_captured = True
        elif label == "lv10":
            active["effect"] = first_value(values) or "待确认"
            effect_captured = True
    return skills, normal_attack


def image_values(items: list[tuple[str, list[str], list[str]]], label: str) -> list[str]:
    return [url for current, _, images in items if current == label for url in images if url]


def suffix(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    return next((ext for ext in (".webp", ".png", ".jpg", ".jpeg") if path.endswith(ext)), ".png")


def download(url: str, output: Path) -> tuple[bool, str]:
    if output.exists() and output.stat().st_size > 0:
        return True, "existing"
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(request(url))
        return True, "downloaded"
    except Exception as exc:
        return False, str(exc)


def parse_payload(payload: dict) -> dict | None:
    raw = payload.get("content")
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def detail_and_content(content_id: int) -> tuple[dict, dict | None]:
    detail = request_json(f"https://www.gamekee.com/v1/content/detail/{content_id}")
    cache_json(DETAIL_DIR / f"detail_{content_id}.json", detail)
    cdn = detail.get("data", {}).get("content_cdn", "")
    if not cdn:
        return detail, None
    payload = request_json(content_url(cdn))
    cache_json(DETAIL_DIR / f"content_{content_id}.json", payload)
    return detail, parse_payload(payload)


def title_is_costume(title: str) -> bool:
    return "：" in title and not title.startswith(("舒恩", "谢芙蒂", "机甲谢芙蒂", "方舟黑色游侠"))


def main() -> None:
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    rows_by_id = {int(row["gamekeeEntryId"]): row for row in rows if row.get("gamekeeEntryId")}

    tree = request_json("https://www.gamekee.com/v1/entry/treesByPid?pid=64581")
    filters = request_json("https://www.gamekee.com/v1/entryFilter/getEntryFilter?entry_id=64599")
    cache_json(TREE_CACHE, tree)
    cache_json(FILTER_CACHE, filters)
    live_entries = [entry for entry in flatten_tree(tree.get("data") or []) if entry.get("content_id")]

    report = {
        "source": {
            "gamekeeTree": "https://www.gamekee.com/v1/entry/treesByPid?pid=64581",
            "gamekeeFilter": "https://www.gamekee.com/v1/entryFilter/getEntryFilter?entry_id=64599",
        },
        "refreshedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "activeRows": len(rows),
        "liveEntries": len(live_entries),
        "skillsUpdated": 0,
        "portraitDownloaded": 0,
        "portraitExisting": 0,
        "costumeDownloaded": 0,
        "costumeExisting": 0,
        "errors": [],
        "unmappedLiveEntries": [],
    }

    for entry_id, row in rows_by_id.items():
        content_id = int(row.get("gamekeeContentId") or 0)
        if not content_id:
            report["errors"].append({"name": row.get("name"), "kind": "missing_content_id"})
            continue
        try:
            _, content = detail_and_content(content_id)
        except Exception as exc:
            report["errors"].append({"name": row.get("name"), "contentId": content_id, "kind": "fetch", "error": str(exc)})
            continue
        if not content:
            report["errors"].append({"name": row.get("name"), "contentId": content_id, "kind": "parse"})
            continue
        items = records(content)
        profile = {PROFILE_LABELS[label]: first_value(values) for label, values, _ in items if label in PROFILE_LABELS and first_value(values)}
        row.update(profile)
        skills, normal_attack = skill_summary(items)
        row["skills"] = skills
        row["normalAttack"] = normal_attack
        row["source"] = {"provider": "GameKee", "contentId": content_id, "url": f"https://www.gamekee.com/nikke/tj/{content_id}.html"}
        report["skillsUpdated"] += len(skills)

        portraits = image_values(items, "立绘")
        costumes = image_values(items, "时装立绘")
        if portraits:
            url = portraits[0]
            output = ASSET_DIR / "portraits" / f"{row['url']}{suffix(url)}"
            ok, status = download(url, output)
            if ok:
                row["gamekeePortraitUrl"] = url
                row["localPortraitFile"] = output.as_posix()
                report["portraitDownloaded" if status == "downloaded" else "portraitExisting"] += 1
            else:
                report["errors"].append({"name": row.get("name"), "kind": "portrait", "error": status})
        if costumes:
            url = costumes[0]
            output = ASSET_DIR / "costume_portraits" / f"{row['url']}{suffix(url)}"
            ok, status = download(url, output)
            if ok:
                row["gamekeeCostumePortraitUrl"] = url
                row["gamekeeLocalCostumePortraitFile"] = output.as_posix()
                report["costumeDownloaded" if status == "downloaded" else "costumeExisting"] += 1
            else:
                report["errors"].append({"name": row.get("name"), "kind": "costume_portrait", "error": status})

    costume_catalog = []
    for entry in live_entries:
        entry_id = int(entry["id"])
        if entry_id in rows_by_id:
            continue
        content_id = int(entry["content_id"])
        try:
            detail, content = detail_and_content(content_id)
        except Exception as exc:
            report["unmappedLiveEntries"].append({"entryId": entry_id, "contentId": content_id, "status": "fetch_failed", "error": str(exc)})
            continue
        title = detail.get("data", {}).get("title", "")
        if not title_is_costume(title):
            report["unmappedLiveEntries"].append({"entryId": entry_id, "contentId": content_id, "title": title, "status": "non_playable_or_unclassified"})
            continue
        items = records(content or {})
        image_urls = image_values(items, "立绘") + image_values(items, "时装立绘")
        image_url = image_urls[0] if image_urls else ""
        record = {"entryId": entry_id, "contentId": content_id, "name": title, "sourceUrl": f"https://www.gamekee.com/nikke/tj/{content_id}.html", "portraitUrl": image_url, "localPortraitFile": "", "status": "only_name"}
        if image_url:
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(content_id))
            output = ASSET_DIR / "skin_catalog" / f"{safe}{suffix(image_url)}"
            ok, status = download(image_url, output)
            if ok:
                record["localPortraitFile"] = output.as_posix()
                record["status"] = "available"
                report["costumeDownloaded" if status == "downloaded" else "costumeExisting"] += 1
            else:
                record["status"] = "download_failed"
                record["error"] = status
                report["errors"].append({"name": title, "kind": "skin_catalog", "error": status})
        costume_catalog.append(record)

    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    SKIN_CATALOG.write_text(json.dumps(costume_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    cache_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
