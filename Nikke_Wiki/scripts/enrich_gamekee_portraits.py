import json
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "assets"
ENHANCED = DATA_DIR / "nikke_character_dictionary_enhanced.json"
PORTRAIT_DIR = ASSET_DIR / "gamekee_character_portraits"
PORTRAIT_MAP = DATA_DIR / "gamekee_character_portrait_urls.json"


# Large standing art URLs confirmed from GameKee rendered character pages.
# Add entries here as more rendered pages are sampled.
CONFIRMED = {
    "Prika": "https://cdnimg-v2.gamekee.com/wiki2.0/pro/1253/images/w_3000/h_3000/1253/4408/2026/4/29/1780051948754_1780050271961_v9u50z3g2r_eamfmr95g9.png",
}


def request(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.gamekee.com/nikke/second/64581",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    rows = json.loads(ENHANCED.read_text(encoding="utf-8"))
    existing = json.loads(PORTRAIT_MAP.read_text(encoding="utf-8")) if PORTRAIT_MAP.exists() else {}
    existing.update(CONFIRMED)
    PORTRAIT_DIR.mkdir(exist_ok=True)

    downloaded = 0
    names = {row["name"] for row in rows}
    for name, url in CONFIRMED.items():
        if name not in names:
            rows.append({
                "name": name,
                "cnName": "普莉卡" if name == "Prika" else name,
                "aliases": "普莉卡" if name == "Prika" else "",
                "url": name.lower().replace(" ", "-"),
                "iconId": "",
                "dotggIconUrl": "",
                "localIconFile": "",
                "gamekeeEntryId": 216838 if name == "Prika" else "",
                "gamekeeCnName": "普莉卡" if name == "Prika" else "",
                "gamekeeIconUrl": "https://cdnimg-v2.gamekee.com/wiki2.0/pro/1253/images/w_310/h_402/1253/4408/2026/4/29/1780050486488_1780050349776_dt5g4ombtc_5b61rwstd2.png" if name == "Prika" else "",
                "wikiNameStatus": "gamekee_only",
                "manufacturer": "",
                "squad": "",
                "class": "",
                "burst": "",
                "rarity": "SSR",
                "weapon": "",
                "element": "",
                "burstGen": "",
            })

    for row in rows:
        url = existing.get(row["name"], "")
        row["gamekeePortraitUrl"] = url
        row["localPortraitFile"] = ""
        if not url:
            continue
        suffix = ".png" if ".png" in url.lower() else ".webp"
        out = PORTRAIT_DIR / f"{row['url']}{suffix}"
        if not out.exists() or out.stat().st_size == 0:
            out.write_bytes(request(url))
            downloaded += 1
        row["localPortraitFile"] = str(out).replace("\\", "/")

    ENHANCED.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    PORTRAIT_MAP.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "portraitUrls": len(existing),
        "downloaded": downloaded,
        "matchedRows": len([r for r in rows if r.get("gamekeePortraitUrl")]),
        "output": str(ENHANCED),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
