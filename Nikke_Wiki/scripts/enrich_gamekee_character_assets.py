from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"
ASSET_ROOT = PROJECT_ROOT / "assets"
ENHANCED = DATA_DIR / "nikke_character_dictionary_enhanced.json"
GAMEKEE_ENTRIES = DATA_DIR / "gamekee_character_entries.json"
TREE_CACHE = DATA_DIR / "gamekee_api_tree_64581.json"
FILTER_CACHE = DATA_DIR / "gamekee_entry_filter_64599.json"
DETAIL_DIR = CACHE_DIR / "gamekee_content_details"
ASSET_DIR = ASSET_ROOT / "gamekee_character_assets"
REPORT = DATA_DIR / "reports" / "gamekee_character_asset_enrichment_report.json"


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "X-Requested-With": "XMLHttpRequest",
    "game-alias": "nikke",
    "Lang": "zh-cn",
    "device-num": "1",
    "Referer": "https://www.gamekee.com/nikke/second/64581",
}


FIELD_BY_INPUT_ID = {
    106: ("gamekeeCompanyCn", "gamekeeCompanyIconUrl", "gamekeeLocalCompanyIconFile"),
    83: ("gamekeeStageCn", "gamekeeStageIconUrl", "gamekeeLocalStageIconFile"),
    97: ("gamekeeWeaponCn", "gamekeeWeaponIconUrl", "gamekeeLocalWeaponIconFile"),
    93: ("gamekeeClassCn", "gamekeeClassIconUrl", "gamekeeLocalClassIconFile"),
    87: ("gamekeeElementCn", "gamekeeElementIconUrl", "gamekeeLocalElementIconFile"),
    79: ("gamekeeRarityCn", "gamekeeRarityIconUrl", "gamekeeLocalRarityIconFile"),
}


def request_json(url: str, *, data: bytes | None = None) -> dict:
    method = "POST" if data is not None else "GET"
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def request_bytes(url: str) -> bytes:
    full_url = normalize_url(url)
    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://www.gamekee.com/nikke/second/64581",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url


def cdn_content_url(url: str) -> str:
    url = normalize_url(url)
    return url.replace("https://api-cdn.gamekee.com/", "https://cdnimg-v2.gamekee.com/")


def clean_image_url(url: str) -> str:
    url = normalize_url(url)
    if "?" in url:
        return url.split("?", 1)[0]
    return url


def slugify(text: str) -> str:
    keep = []
    for ch in text.lower():
        if ch.isalnum():
            keep.append(ch)
        elif ch in " -_:.":
            keep.append("-")
    value = "".join(keep).strip("-")
    while "--" in value:
        value = value.replace("--", "-")
    return value or "asset"


def suffix_for(url: str) -> str:
    path = urllib.parse.urlparse(clean_image_url(url)).path.lower()
    for suffix in [".png", ".webp", ".jpg", ".jpeg"]:
        if path.endswith(suffix):
            return suffix
    return ".png"


def load_or_fetch_json(path: Path, url: str) -> dict:
    if path.exists() and path.stat().st_size > 0:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    data = request_json(url)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def curl_json(url: str, out: Path, referer: str) -> dict | None:
    if out.exists() and out.stat().st_size > 0:
        try:
            return json.loads(out.read_text(encoding="utf-8-sig"))
        except Exception:
            out.unlink(missing_ok=True)
    cmd = [
        "curl.exe",
        "-s",
        "-L",
        "--compressed",
        "-A",
        HEADERS["User-Agent"],
        "-H",
        "Accept: application/json,text/plain,*/*",
        "-H",
        "X-Requested-With: XMLHttpRequest",
        "-H",
        "game-alias: nikke",
        "-H",
        "Lang: zh-cn",
        "-H",
        "device-num: 1",
        "-H",
        f"Referer: {referer}",
        url,
        "-o",
        str(out),
        "--max-time",
        "45",
    ]
    result = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"[warn] curl failed {url}: {result.stderr.strip()}")
        return None
    try:
        return json.loads(out.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        print(f"[warn] json parse failed {out}: {exc}")
        return None


def flatten_tree(nodes: list[dict]) -> list[dict]:
    result = []
    for node in nodes:
        result.append(node)
        child = node.get("child") or []
        if child:
            result.extend(flatten_tree(child))
    return result


def filter_lookup(filter_data: dict) -> tuple[dict[int, str], dict[int, dict[str, dict]], dict[str, list[dict]]]:
    root = filter_data["data"]
    input_name_by_id: dict[int, str] = {}
    option_by_input: dict[int, dict[str, dict]] = {}
    for group in root["entry_filter"]:
        input_id = int(group["id"])
        input_name_by_id[input_id] = group["name"]
        option_by_input[input_id] = {}
        for child in group.get("children") or []:
            option_by_input[input_id][str(child["id"])] = child
    return input_name_by_id, option_by_input, root["entry_filter_attr"]


def asset_path(kind: str, row_url: str, url: str) -> Path:
    return ASSET_DIR / kind / f"{row_url}{suffix_for(url)}"


def shared_asset_path(kind: str, label: str, url: str) -> Path:
    return ASSET_DIR / kind / f"{slugify(label)}{suffix_for(url)}"


def download(url: str, out: Path) -> bool:
    if not url:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return True
    try:
        out.write_bytes(request_bytes(url))
        time.sleep(0.03)
        return out.exists() and out.stat().st_size > 0
    except Exception as exc:
        print(f"[warn] download failed {url}: {exc}")
        return False


def walk_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_strings(child)
    elif isinstance(value, str):
        yield value


def extract_portrait_urls(content_payload: dict) -> tuple[str, str]:
    try:
        content = json.loads(content_payload.get("content", "{}"))
    except Exception:
        return "", ""
    style_data = content.get("styleData") or []
    portrait_urls: list[str] = []
    for style in style_data:
        candidates = []
        for text in walk_strings(style):
            if "cdnimg-v2.gamekee.com" not in text and not text.startswith("//cdnimg-v2.gamekee.com"):
                continue
            if "images/" not in text:
                continue
            if ".gif" in text.lower():
                continue
            score = 0
            if "w_3000" in text or "h_3000" in text:
                score += 100
            if "w_1500" in text or "h_1500" in text:
                score += 40
            if "/pro/1253/images/" in text:
                score += 10
            candidates.append((score, text))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            url = clean_image_url(candidates[0][1])
            if url and url not in portrait_urls:
                portrait_urls.append(url)
    normal = portrait_urls[0] if portrait_urls else ""
    costume = portrait_urls[1] if len(portrait_urls) > 1 else ""
    return normal, costume


def main() -> None:
    ASSET_DIR.mkdir(exist_ok=True)
    DETAIL_DIR.mkdir(exist_ok=True)

    rows = json.loads(ENHANCED.read_text(encoding="utf-8"))
    entries = json.loads(GAMEKEE_ENTRIES.read_text(encoding="utf-8"))

    tree_data = load_or_fetch_json(TREE_CACHE, "https://www.gamekee.com/v1/entry/treesByPid?pid=64581")
    tree_entries = flatten_tree(tree_data["data"])
    tree_by_id = {int(item["id"]): item for item in tree_entries}

    filter_data = load_or_fetch_json(FILTER_CACHE, "https://www.gamekee.com/v1/entryFilter/getEntryFilter?entry_id=64599")
    _, option_by_input, attr_by_entry_id = filter_lookup(filter_data)

    entry_by_id = {int(e["gamekeeEntryId"]): e for e in entries}
    content_id_by_entry = {
        int(item["id"]): item.get("content_id")
        for item in tree_entries
        if item.get("content_id")
    }

    coverage = {
        "rows": len(rows),
        "teamCardUrl": 0,
        "stage": 0,
        "class": 0,
        "company": 0,
        "weapon": 0,
        "element": 0,
        "rarity": 0,
        "portrait": 0,
        "missingGameKeeEntryId": [],
        "missingFilterAttr": [],
        "downloadFailures": [],
    }

    # Download shared filter icons once and record their local paths.
    local_icon_by_option: dict[tuple[int, str], str] = {}
    for input_id, options in option_by_input.items():
        for option_id, option in options.items():
            url = clean_image_url(option.get("icon", ""))
            if not url:
                continue
            kind_label = FIELD_BY_INPUT_ID.get(input_id, (f"filter_{input_id}", "", ""))[0]
            out = shared_asset_path(kind_label, f"{input_id}_{option_id}_{option.get('name', '')}", url)
            if download(url, out):
                local_icon_by_option[(input_id, option_id)] = str(out).replace("\\", "/")

    for row in rows:
        entry_id_raw = row.get("gamekeeEntryId")
        if not entry_id_raw:
            coverage["missingGameKeeEntryId"].append(row.get("name"))
            continue
        entry_id = int(entry_id_raw)
        row["gamekeeContentId"] = content_id_by_entry.get(entry_id, row.get("gamekeeContentId", ""))

        tree_entry = tree_by_id.get(entry_id) or {}
        entry = entry_by_id.get(entry_id) or {}
        content_id = row.get("gamekeeContentId") or content_id_by_entry.get(entry_id, "")
        row["gamekeeContentId"] = content_id

        detail_payload = None
        if content_id:
            detail_path = DETAIL_DIR / f"detail_{content_id}.json"
            try:
                detail_payload = load_or_fetch_json(detail_path, f"https://www.gamekee.com/v1/content/detail/{content_id}")
            except Exception as exc:
                print(f"[warn] detail failed {row.get('name')}: {exc}")
                detail_payload = None
        content_cdn = ""
        if detail_payload and detail_payload.get("code") == 0:
            content_cdn = detail_payload.get("data", {}).get("content_cdn", "")
        if content_cdn:
            content_url = cdn_content_url(content_cdn)
            content_path = DETAIL_DIR / f"content_{content_id}.json"
            content_payload = curl_json(content_url, content_path, f"https://www.gamekee.com/nikke/tj/{content_id}.html")
            if content_payload:
                portrait_url, costume_portrait_url = extract_portrait_urls(content_payload)
                if portrait_url:
                    row["gamekeePortraitUrl"] = portrait_url
                    out = asset_path("portraits", row["url"], portrait_url)
                    if download(portrait_url, out):
                        row["localPortraitFile"] = str(out).replace("\\", "/")
                if costume_portrait_url:
                    row["gamekeeCostumePortraitUrl"] = costume_portrait_url
                    out = asset_path("costume_portraits", row["url"], costume_portrait_url)
                    if download(costume_portrait_url, out):
                        row["gamekeeLocalCostumePortraitFile"] = str(out).replace("\\", "/")

        team_card_url = clean_image_url(tree_entry.get("icon") or entry.get("icon") or row.get("gamekeeIconUrl", ""))
        row["gamekeeTeamCardUrl"] = team_card_url
        if team_card_url:
            out = asset_path("team_cards", row["url"], team_card_url)
            if download(team_card_url, out):
                row["gamekeeLocalTeamCardFile"] = str(out).replace("\\", "/")
                coverage["teamCardUrl"] += 1
            else:
                coverage["downloadFailures"].append({"name": row.get("name"), "kind": "teamCard", "url": team_card_url})

        attrs = attr_by_entry_id.get(str(entry_id), [])
        if not attrs:
            coverage["missingFilterAttr"].append({"name": row.get("name"), "entryId": entry_id})

        for attr in attrs:
            input_id = int(attr.get("input_id", 0))
            if input_id not in FIELD_BY_INPUT_ID:
                continue
            value_ids = [str(v) for v in (attr.get("value") or []) if str(v) not in {"", "0"}]
            if not value_ids:
                continue
            option = option_by_input.get(input_id, {}).get(value_ids[0], {})
            if not option:
                continue
            name_key, icon_key, local_key = FIELD_BY_INPUT_ID[input_id]
            icon_url = clean_image_url(option.get("icon", ""))
            row[name_key] = option.get("name", "")
            row[icon_key] = icon_url
            row[local_key] = local_icon_by_option.get((input_id, value_ids[0]), "")

        if row.get("gamekeeStageCn"):
            coverage["stage"] += 1
        if row.get("gamekeeClassCn"):
            coverage["class"] += 1
        if row.get("gamekeeCompanyCn"):
            coverage["company"] += 1
        if row.get("gamekeeWeaponCn"):
            coverage["weapon"] += 1
        if row.get("gamekeeElementCn"):
            coverage["element"] += 1
        if row.get("gamekeeRarityCn"):
            coverage["rarity"] += 1
        if row.get("gamekeePortraitUrl"):
            coverage["portrait"] += 1

    coverage["costumePortrait"] = len([r for r in rows if r.get("gamekeeCostumePortraitUrl")])

    ENHANCED.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(coverage, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
