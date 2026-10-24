from __future__ import annotations

import json
import time
from pathlib import Path

from refresh_character_cards import ASSET_DIR, download, first_value, parse_payload, records, suffix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DETAIL_DIR = PROJECT_ROOT / "cache" / "gamekee_content_details"
OUT = PROJECT_ROOT / "data" / "non_playable_character_cards.json"
REPORT = PROJECT_ROOT / "data" / "reports" / "non_playable_character_cards_report.json"
ENTRIES = {
    589285: {"entryId": 120033, "aliases": []},
    619532: {"entryId": 147300, "aliases": []},
    684097: {"entryId": 198648, "aliases": []},
    708686: {"entryId": 217280, "aliases": ["方舟游侠"]},
}
FIELDS = {"\u7a00\u6709\u5ea6": "rarity", "\u5b9e\u88c5\u65e5\u671f": "pagePublishedAt", "\u4f01\u4e1a": "company", "\u90e8\u961f": "squad", "\u9636\u6bb5": "stage", "\u5c5e\u6027": "element", "\u804c\u4e1a": "class", "\u6b66\u5668": "weapon", "\u6b66\u5668\uff08\u540d\uff09": "weaponName", "\u7b80\u4ecb": "description"}
NAME_LABEL = "\u89d2\u8272\u540d\u79f0"


def load_content(content_id: int) -> dict:
    payload = json.loads((DETAIL_DIR / f"content_{content_id}.json").read_text(encoding="utf-8"))
    content = parse_payload(payload)
    if not content:
        raise ValueError("unparseable cached content")
    return content


def skill_groups(items: list[tuple[str, list[str], list[str]]]) -> dict:
    prefixes = {"\u6280\u80fd1\u540d\u79f0": "skill1", "\u6280\u80fd2\u540d\u79f0": "skill2", "\u7206\u88c2\u6280\u80fd\u540d\u79f0": "burstSkill", "\u7206\u88c2\u6280\u80fd": "burstSkill"}
    out, active = {}, None
    for label, values, _ in items:
        if label in prefixes:
            active = {"name": first_value(values), "type": "待确认", "cooldown": "待确认", "effect": "待确认"}
            out[prefixes[label]] = active
        elif active and label == "冷却时间":
            active["cooldown"] = first_value(values) or "待确认"
        elif active and label == "技能类型":
            active["type"] = first_value(values) or "待确认"
        elif active and label == "lv10":
            active["effect"] = first_value(values) or "待确认"
    return out


def main() -> None:
    cards, failures = [], []
    for content_id, meta in ENTRIES.items():
        try:
            items = records(load_content(content_id))
            values = {label: first_value(row_values) for label, row_values, _ in items}
            portrait = next((images[0] for label, _, images in items if label == "部队成员1" and images), "")
            name = values[NAME_LABEL]
            local_file = ASSET_DIR / "non_playable_cards" / f"{content_id}{suffix(portrait)}"
            downloaded = "not_available"
            if portrait:
                ok, downloaded = download(portrait, local_file)
                if not ok:
                    raise ValueError(downloaded)
            card = {"name": name, "aliases": meta["aliases"], "characterCategory": "non_playable", "gamekeeEntryId": meta["entryId"], "gamekeeContentId": content_id, "source": {"provider": "GameKee", "url": f"https://www.gamekee.com/nikke/tj/{content_id}.html"}, "skills": skill_groups(items), "portraitUrl": portrait, "localPortraitFile": local_file.as_posix() if portrait else ""}
            card.update({field: values.get(label, "待确认") or "待确认" for label, field in FIELDS.items()})
            cards.append(card)
        except Exception as exc:
            failures.append({"contentId": content_id, "error": str(exc)})
    OUT.write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps({"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cards": len(cards), "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cards": len(cards), "failures": failures}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
