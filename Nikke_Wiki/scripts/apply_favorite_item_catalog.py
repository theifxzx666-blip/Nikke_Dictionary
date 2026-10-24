import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARY = DATA_DIR / "nikke_character_dictionary_enhanced.json"
CATALOG = DATA_DIR / "nikke_favorite_items.json"
REPORT = DATA_DIR / "reports" / "favorite_item_update_report.json"


def main() -> None:
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    items = {item["character"]: item for item in catalog["items"]}
    unmatched = sorted(set(items) - {row.get("name") for row in rows})
    confirmed = 0
    for row in rows:
        item = items.get(row.get("name"))
        if item:
            row["favoriteItem"] = {
                "status": item["status"],
                "itemName": item["itemName"],
                "cnReleased": item["cnReleased"],
                "sourceUrl": item["sourceUrl"],
                "note": item["note"],
                "skills": item.get("skills", {}),
            }
            confirmed += 1
        else:
            row["favoriteItem"] = {"status": "待确认", "itemName": "", "cnReleased": "待确认", "sourceUrl": "", "note": "未发现可追溯的珍藏品资料。"}
    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps({"rows": len(rows), "confirmed": confirmed, "unmatched": unmatched, "catalog": str(CATALOG)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "confirmed": confirmed, "unmatched": unmatched}, ensure_ascii=False))


if __name__ == "__main__":
    main()
