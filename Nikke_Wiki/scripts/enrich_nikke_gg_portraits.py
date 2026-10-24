"""Collect Nikke.gg standing-art portraits and bind them to character assets."""

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT / "data" / "character_repository"
ASSET_ROOT = REPOSITORY / "assets" / "characters"
CACHE = ROOT / "cache"
PATTERN = re.compile(r"https://static\.dotgg\.gg/nikke/characters-big/[0-9]+\.(?:webp|png|jpg)")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_page(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "NIKKE-Wiki-maintenance/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def download(url: str, path: Path) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "NIKKE-Wiki-maintenance/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
        if len(payload) < 1000:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Add Nikke.gg standing-art portraits")
    parser.add_argument("--apply", action="store_true", help="fetch missing pages and download portraits")
    args = parser.parse_args()
    canonical_path = REPOSITORY / "canonical" / "characters.json"
    canonical = read_json(canonical_path)
    found = downloaded = failed = 0
    rows = []
    for record in canonical["characters"]:
        identity = record["identity"]
        slug = identity["dictionarySlug"]
        page_path = CACHE / f"dotgg_{slug}.html"
        html = page_path.read_text(encoding="utf-8", errors="ignore") if page_path.is_file() else ""
        if not html and args.apply:
            try:
                html = fetch_page(identity["evidence"]["nikkeGg"])
                page_path.write_text(html, encoding="utf-8")
            except Exception:
                html = ""
        match = PATTERN.search(html)
        url = match.group(0) if match else ""
        target = ASSET_ROOT / slug / "nikke_gg_portrait.webp"
        status = "missing"
        if url:
            found += 1
            status = "available"
            if args.apply and (not target.is_file() or target.stat().st_size < 1000):
                if download(url, target):
                    downloaded += 1
                else:
                    status = "download_failed"
                    failed += 1
            if args.apply:
                record.setdefault("assets", {})["nikkeGgPortrait"] = {"url": url, "file": f"assets/characters/{slug}/nikke_gg_portrait.webp", "status": "available" if target.is_file() else "download_failed"}
        elif args.apply:
            record.setdefault("assets", {})["nikkeGgPortrait"] = {"url": "", "file": f"assets/characters/{slug}/nikke_gg_portrait.webp", "status": "missing"}
        rows.append({"dictionarySlug": slug, "url": url, "file": f"assets/characters/{slug}/nikke_gg_portrait.webp", "status": status})
        time.sleep(0.05)
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "apply": args.apply, "characterCount": len(rows), "found": found, "downloaded": downloaded, "failed": failed, "missing": [row["dictionarySlug"] for row in rows if row["status"] == "missing"], "portraits": rows}
    report_path = REPOSITORY / "reports" / ("nikke_gg_portraits_latest.json" if args.apply else "nikke_gg_portraits_dry_run.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.apply:
        canonical["generatedAt"] = report["generatedAt"]
        canonical_path.write_text(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("apply", "characterCount", "found", "downloaded", "failed", "missing")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
