from __future__ import annotations

import json
import time
from pathlib import Path

from refresh_character_cards import ASSET_DIR, DICTIONARY, PROFILE_LABELS, apply_gamekee_canonical_fields, download, first_value, flatten_tree, normalize_url, parse_payload, records, skill_summary, suffix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DETAIL_DIR = PROJECT_ROOT / "cache" / "gamekee_content_details"
REPORT = PROJECT_ROOT / "data" / "reports" / "targeted_character_card_repair_report.json"
TARGET_CONTENT_IDS = {705512, 706696}
TREE_CACHE = PROJECT_ROOT / "data" / "gamekee_api_tree_64581.json"


def main() -> None:
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    tree = json.loads(TREE_CACHE.read_text(encoding="utf-8"))
    tree_entries = {int(entry["content_id"]): entry for entry in flatten_tree(tree.get("data") or []) if entry.get("content_id")}
    repaired, failures = [], []
    for row in rows:
        content_id = int(row.get("gamekeeContentId") or 0)
        if content_id not in TARGET_CONTENT_IDS:
            continue
        try:
            payload = json.loads((DETAIL_DIR / f"content_{content_id}.json").read_text(encoding="utf-8"))
            content = parse_payload(payload)
            if not content:
                raise ValueError("unparseable cached content")
            items = records(content)
            row.update({PROFILE_LABELS[label]: first_value(values) for label, values, _ in items if label in PROFILE_LABELS and first_value(values)})
            row["skills"], row["normalAttack"] = skill_summary(items)
            apply_gamekee_canonical_fields(row)
            icon_url = normalize_url(tree_entries.get(content_id, {}).get("icon", "") or row.get("gamekeeIconUrl", ""))
            if icon_url:
                icon_file = PROJECT_ROOT / "assets" / "nikke_character_icons" / f"gamekee_{content_id}{suffix(icon_url)}"
                ok, status = download(icon_url, icon_file)
                if not ok:
                    raise ValueError(status)
                row["gamekeeIconUrl"] = icon_url
                row["localIconFile"] = icon_file.as_posix()
            row["source"] = {"provider": "GameKee", "contentId": content_id, "url": f"https://www.gamekee.com/nikke/{content_id}"}
            repaired.append({"name": row["name"], "contentId": content_id, "skillEffects": {key: skill["effect"] for key, skill in row["skills"].items()}})
        except Exception as exc:
            failures.append({"name": row.get("name", ""), "contentId": content_id, "error": str(exc)})
    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repaired": repaired, "failures": failures}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
