from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from refresh_character_cards import (
    ASSET_DIR,
    apply_gamekee_canonical_fields,
    DICTIONARY,
    FILTER_CACHE,
    TREE_CACHE,
    PROFILE_LABELS,
    cache_json,
    detail_and_content,
    download,
    first_value,
    flatten_tree,
    image_values,
    normalize_url,
    records,
    request_json,
    skill_summary,
    suffix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
STATE_DIR = DATA_DIR / "character_library_state"
ONLINE_SNAPSHOT = STATE_DIR / "online_index_snapshot.json"
PROCESSED_INDEX = STATE_DIR / "processed_versions.json"
ASSET_INDEX = STATE_DIR / "asset_download_index.json"
RETRY_QUEUE = STATE_DIR / "retry_queue.json"
LATEST_REPORT = DATA_DIR / "reports" / "character_library_update_report.json"
REPORT_DIR = DATA_DIR / "character_library_reports"
NON_PLAYABLE_ENTRIES = {
    120033: "NPC/剧情角色：谢芙蒂",
    147300: "NPC/剧情角色：舒恩",
    198648: "NPC/剧情角色：机甲谢芙蒂",
}
# 皮肤/时装条目：关联本体角色（data/gamekee_costume_catalog.json），不作为独立可操作角色录入
# 2026-08-12 用户确认：灰姑娘：琉璃波光/玛律恰那：海洋进修/拉普拉斯：究极英雄/麦斯威尔：平凡技师
# 为独立可操作角色（characterCategory=playable），已恢复主表，不再映射为皮肤
MAPPED_COSTUME_ENTRIES = {}
# 已由 Nikke.gg 角色列表和 GameKee 详情页交叉确认的可操作角色。头像仍以
# Nikke.gg 可用的 128x128 静态资源为准，未公开时明确保留待确认状态。
CONFIRMED_PLAYABLE_ENTRIES = {
    221057: {"name": "Queen (Makoto)", "cnName": "QUEEN（真）", "slug": "queen-makoto"},
    221387: {"name": "Yukiko", "cnName": "雪子", "slug": "yukiko"},
    221388: {"name": "Aigis", "cnName": "埃葵斯", "slug": "aigis"},
}
TREE_URL = "https://www.gamekee.com/v1/entry/treesByPid?pid=64581"
FILTER_URL = "https://www.gamekee.com/v1/entryFilter/getEntryFilter?entry_id=64599"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def entry_version(entry: dict) -> str:
    stable = {
        "entryId": int(entry["id"]),
        "contentId": int(entry["content_id"]),
        "icon": entry.get("icon", ""),
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def online_index(tree: dict) -> dict[str, dict]:
    return {
        str(entry["id"]): {
            "entryId": int(entry["id"]),
            "contentId": int(entry["content_id"]),
            "icon": entry.get("icon", ""),
            "version": entry_version(entry),
        }
        for entry in flatten_tree(tree.get("data") or [])
        if entry.get("content_id")
    }


def base_report(index: dict[str, dict], rows: list[dict], processed: dict, previous_index: dict[str, dict]) -> dict:
    local_ids = {str(row["gamekeeEntryId"]): row for row in rows if row.get("gamekeeEntryId")}
    online_ids = set(index)
    local_id_set = set(local_ids)
    unclassified_ids = online_ids - local_id_set
    new_ids = sorted((entry_id for entry_id in unclassified_ids if int(entry_id) not in NON_PLAYABLE_ENTRIES and int(entry_id) not in MAPPED_COSTUME_ENTRIES), key=int)
    missing_online = sorted(local_id_set - online_ids, key=int)
    changed = []
    unchanged = []
    first_baseline = not processed
    for entry_id in sorted(online_ids & local_id_set, key=int):
        current = index[entry_id]
        known = processed.get(entry_id, {})
        row = local_ids[entry_id]
        required = ("gamekeeCompanyCn", "gamekeeSquadCn", "gamekeeStageCn", "gamekeeElementCn", "gamekeeWeaponCn")
        incomplete = any(not row.get(key) for key in required) or not all(row.get("skills", {}).get(key) for key in ("skill1", "skill2", "burstSkill"))
        if incomplete:
            changed.append({"entryId": int(entry_id), "contentId": current["contentId"], "name": row.get("name", ""), "reason": "local_incomplete"})
        elif not first_baseline and known.get("version") != current["version"] and (
            known.get("fingerprintVersion") == 2
            or previous_index.get(entry_id, {}).get("contentId") != current["contentId"]
            or previous_index.get(entry_id, {}).get("icon") != current["icon"]
        ):
            changed.append({"entryId": int(entry_id), "contentId": current["contentId"], "name": row.get("name", ""), "reason": "online_version_changed"})
        else:
            unchanged.append(entry_id)
    return {
        "schemaVersion": 1,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": {"tree": TREE_URL, "filter": FILTER_URL},
        "localPlayableRows": len(rows),
        "onlineEntries": len(index),
        "newEntries": [{"entryId": int(entry_id), "contentId": index[entry_id]["contentId"]} for entry_id in new_ids],
        "classifiedNonPlayableEntries": [
            {"entryId": int(entry_id), "contentId": index[entry_id]["contentId"], "classification": NON_PLAYABLE_ENTRIES[int(entry_id)]}
            for entry_id in sorted(unclassified_ids, key=int) if int(entry_id) in NON_PLAYABLE_ENTRIES
        ],
        "mappedCostumeEntries": [
            {"entryId": int(entry_id), "contentId": index[entry_id]["contentId"]}
            for entry_id in sorted(unclassified_ids, key=int) if int(entry_id) in MAPPED_COSTUME_ENTRIES
        ],
        "missingOnlineEntries": [{"entryId": int(entry_id), "name": local_ids[entry_id].get("name", "")} for entry_id in missing_online],
        "changedEntries": changed,
        "skippedUnchanged": len(unchanged),
        "detailRequestsPlanned": len(changed),
        "assetDownloadsPlanned": 0,
        "baselineInitialization": first_baseline,
        "versionFingerprint": "contentId+icon",
    }


def update_row(row: dict, asset_index: dict) -> tuple[bool, list[dict]]:
    failures = []
    content_id = int(row["gamekeeContentId"])
    _, content = detail_and_content(content_id)
    if not content:
        raise ValueError("GameKee content payload is empty or unparsable")
    items = records(content)
    row.update({PROFILE_LABELS[label]: first_value(values) for label, values, _ in items if label in PROFILE_LABELS and first_value(values)})
    row["skills"], row["normalAttack"] = skill_summary(items)
    row["source"] = {"provider": "GameKee", "contentId": content_id, "url": f"https://www.gamekee.com/nikke/tj/{content_id}.html"}
    for label, url_field, file_field, folder in (
        ("立绘", "gamekeePortraitUrl", "localPortraitFile", "portraits"),
        ("时装立绘", "gamekeeCostumePortraitUrl", "gamekeeLocalCostumePortraitFile", "costume_portraits"),
    ):
        urls = image_values(items, label)
        if not urls:
            continue
        url = urls[0]
        output = ASSET_DIR / folder / f"{row['url']}{suffix(url)}"
        ok, status = download(url, output)
        if ok:
            row[url_field] = url
            row[file_field] = output.as_posix()
            asset_index[row["url"] + ":" + folder] = {"url": url, "file": output.as_posix(), "status": status}
        else:
            failures.append({"name": row.get("name"), "kind": folder, "url": url, "error": status})
    return True, failures


def promote_new_entry(entry: dict, asset_index: dict) -> tuple[dict, list[dict]]:
    entry_id = int(entry["entryId"])
    confirmed = CONFIRMED_PLAYABLE_ENTRIES[entry_id]
    content_id = int(entry["contentId"])
    _, content = detail_and_content(content_id)
    if not content:
        raise ValueError("GameKee content payload is empty or unparsable")

    items = records(content)
    row = {
        "name": confirmed["name"],
        "cnName": confirmed["cnName"],
        "aliases": confirmed["cnName"],
        "url": confirmed["slug"],
        "gamekeeEntryId": entry_id,
        "gamekeeContentId": content_id,
        "gamekeeIconUrl": normalize_url(entry.get("icon", "")),
        "gamekeeTeamCardUrl": normalize_url(entry.get("icon", "")),
        "wikiNameStatus": "matched",
        "avatarStatus": "pending_confirmation",
        "avatarSource": "Nikke.gg_detail_pending_static_avatar",
        "dotggIconUrl": "",
        "localIconFile": "",
        "cnReleased": "待确认",
        "releaseBasis": "GameKee已列出资料；国服状态待确认",
        "favoriteItem": {"status": "待确认", "itemName": "", "cnReleased": "待确认", "sourceUrl": "", "note": "未核对珍藏品资料"},
        "costumes": [],
        "source": {"provider": "GameKee", "contentId": content_id, "url": f"https://www.gamekee.com/nikke/tj/{content_id}.html"},
    }
    row.update({PROFILE_LABELS[label]: first_value(values) for label, values, _ in items if label in PROFILE_LABELS and first_value(values)})
    apply_gamekee_canonical_fields(row)
    row["skills"], row["normalAttack"] = skill_summary(items)

    failures = []
    if row["gamekeeTeamCardUrl"]:
        output = ASSET_DIR / "team_cards" / f"{row['url']}{suffix(row['gamekeeTeamCardUrl'])}"
        ok, status = download(row["gamekeeTeamCardUrl"], output)
        if ok:
            row["gamekeeLocalTeamCardFile"] = output.as_posix()
            asset_index[row["url"] + ":team_cards"] = {"url": row["gamekeeTeamCardUrl"], "file": output.as_posix(), "status": status}
        else:
            failures.append({"entryId": entry_id, "name": row["name"], "kind": "team_cards", "url": row["gamekeeTeamCardUrl"], "error": status})
    return row, failures


def validate(rows: list[dict]) -> dict:
    required = ("gamekeeCompanyCn", "gamekeeSquadCn", "gamekeeStageCn", "gamekeeElementCn", "gamekeeWeaponCn")
    missing_fields = [row["name"] for row in rows if any(not row.get(key) for key in required)]
    missing_skills = [row["name"] for row in rows if not all(row.get("skills", {}).get(key) for key in ("skill1", "skill2", "burstSkill"))]
    bad_paths = [row["name"] for row in rows if row.get("localPortraitFile") and not Path(row["localPortraitFile"]).exists()]
    favorite = [row for row in rows if row.get("favoriteItem", {}).get("status") == "已确认"]
    favorite_missing = [row["name"] for row in favorite if len(row.get("favoriteItem", {}).get("skills", {})) != 3]
    return {"missingRequiredFields": missing_fields, "missingSkillGroups": missing_skills, "missingPortraitPaths": bad_paths, "favoriteItemSkillMissing": favorite_missing}


def main() -> None:
    parser = argparse.ArgumentParser(description="NIKKE 角色资料库增量维护入口")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="仅同步轻量索引并输出差异，不写角色资料或素材")
    mode.add_argument("--apply", action="store_true", help="仅处理 dry-run 判定为变更的既有角色")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_json(DICTIONARY, [])
    processed = load_json(PROCESSED_INDEX, {})
    retry_queue = load_json(RETRY_QUEUE, [])
    tree = request_json(TREE_URL)
    filters = request_json(FILTER_URL)
    index = online_index(tree)
    previous_snapshot = load_json(ONLINE_SNAPSHOT, {}).get("entries", {})
    report = base_report(index, rows, processed, previous_snapshot)
    report["mode"] = "dry-run" if args.dry_run else "apply"
    report["retryQueueBefore"] = len(retry_queue)

    if args.dry_run:
        report["validation"] = validate(rows)
        report["note"] = "首次运行会为本地完整角色建立版本基线，仅请求本地字段或技能组不完整的角色详情。"
    else:
        row_by_id = {str(row["gamekeeEntryId"]): row for row in rows if row.get("gamekeeEntryId")}
        failures = []
        updated = []
        asset_index = load_json(ASSET_INDEX, {})
        promoted = []
        for entry in report["newEntries"]:
            if entry["entryId"] not in CONFIRMED_PLAYABLE_ENTRIES:
                failures.append({"entryId": entry["entryId"], "kind": "classification", "error": "未确认的新增条目，未自动录入"})
                continue
            try:
                row, item_failures = promote_new_entry(index[str(entry["entryId"])], asset_index)
                rows.append(row)
                row_by_id[str(entry["entryId"])] = row
                failures.extend(item_failures)
                promoted.append(row["name"])
            except Exception as exc:
                failures.append({"entryId": entry["entryId"], "name": CONFIRMED_PLAYABLE_ENTRIES[entry["entryId"]]["name"], "kind": "promotion", "error": str(exc)})
        for change in report["changedEntries"]:
            entry_id = str(change["entryId"])
            try:
                _, item_failures = update_row(row_by_id[entry_id], asset_index)
                failures.extend(item_failures)
                updated.append(change["name"])
            except Exception as exc:
                failures.append({"entryId": change["entryId"], "name": change["name"], "kind": "detail", "error": str(exc)})
        for entry_id, item in index.items():
            if entry_id in row_by_id and entry_id not in {str(f.get("entryId")) for f in failures}:
                processed[entry_id] = {"version": item["version"], "fingerprintVersion": 2, "contentId": item["contentId"], "processedAt": report["generatedAt"]}
        write_json(DICTIONARY, rows)
        write_json(PROCESSED_INDEX, processed)
        write_json(ASSET_INDEX, asset_index)
        write_json(RETRY_QUEUE, failures)
        report.update({"promotedEntries": promoted, "updatedEntries": updated, "failedEntries": failures, "retryQueueAfter": len(failures), "validation": validate(rows)})
        # Exports are regenerated only after a successful incremental write.
        from export_nikke_character_tables import main as export_main
        export_main()

    write_json(ONLINE_SNAPSHOT, {"generatedAt": report["generatedAt"], "entries": index})
    write_json(LATEST_REPORT, report)
    write_json(REPORT_DIR / f"update_{time.strftime('%Y%m%d_%H%M%S')}_{report['mode']}.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
