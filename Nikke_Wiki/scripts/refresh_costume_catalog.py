from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from refresh_character_cards import ASSET_DIR, DICTIONARY, download, parse_payload, records, suffix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PROJECT_ROOT / "data" / "gamekee_costume_catalog.json"
DETAIL_DIR = PROJECT_ROOT / "cache" / "gamekee_content_details"
REPORT = PROJECT_ROOT / "data" / "reports" / "costume_catalog_refresh_report.json"
DISPLAY_LABEL = "角色展示"
# 2026-08-12 用户确认：711133/711739/713891/713899 为独立可操作角色（已恢复主表），不再视为皮肤
PARENT_BY_CONTENT_ID = {}


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def display_image(content_id: int) -> str:
    path = DETAIL_DIR / f"content_{content_id}.json"
    payload = load_json(path, {})
    content = parse_payload(payload)
    if not content:
        return ""
    for label, _, images in records(content):
        if label == DISPLAY_LABEL:
            return next((url for url in images if suffix(url) in {".png", ".webp", ".jpg", ".jpeg"}), "")
    return ""


def display_video(content_id: int) -> str:
    payload = load_json(DETAIL_DIR / f"content_{content_id}.json", {})
    content = parse_payload(payload)
    if not content:
        return ""
    for row in content.get("baseData", []):
        text_cells = [cell.get("value", "") for cell in row if cell.get("type") == "text"]
        if not text_cells or text_cells[0] != DISPLAY_LABEL:
            continue
        for cell in row:
            if cell.get("type") == "video" and isinstance(cell.get("value"), str):
                return cell["value"] if cell["value"].startswith("https:") else "https:" + cell["value"]
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh mapped GameKee costume portraits from local detail cache.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    catalog = load_json(CATALOG, [])
    rows = load_json(DICTIONARY, [])
    rows_by_name = {row.get("name"): row for row in rows}
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "mode": "dry-run" if args.dry_run else "apply", "processed": [], "failures": []}

    for item in catalog:
        content_id = int(item["contentId"])
        parent_name = PARENT_BY_CONTENT_ID.get(content_id)
        if not parent_name or parent_name not in rows_by_name:
            report["failures"].append({"contentId": content_id, "name": item.get("name", ""), "reason": "unmapped_parent"})
            continue
        portrait_url = display_image(content_id)
        row = rows_by_name[parent_name]
        local_file = ASSET_DIR / "skin_catalog" / f"{row['url']}_{content_id}{suffix(portrait_url)}" if portrait_url else Path()
        entry = {
            "name": item["name"],
            "contentId": content_id,
            "sourceUrl": item["sourceUrl"],
            "portraitUrl": portrait_url,
            "localPortraitFile": local_file.as_posix() if portrait_url else "",
            "status": "available" if portrait_url else "only_name",
            "parentCharacter": parent_name,
            "displayVideoUrl": display_video(content_id),
        }
        status = "planned" if portrait_url else "no_static_portrait"
        if args.apply and portrait_url:
            ok, status = download(portrait_url, local_file)
            if not ok:
                report["failures"].append({"contentId": content_id, "name": item["name"], "reason": status})
                continue
        if args.apply:
            item.update(entry)
            existing = [costume for costume in row.get("costumes", []) if int(costume.get("contentId", 0)) != content_id]
            row["costumes"] = existing + [entry]
        report["processed"].append({"contentId": content_id, "name": item["name"], "parentCharacter": parent_name, "portraitUrl": portrait_url, "localPortraitFile": local_file.as_posix() if portrait_url else "", "download": status})

    if args.apply:
        write_json(CATALOG, catalog)
        write_json(DICTIONARY, rows)
    write_json(REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
