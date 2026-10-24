from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache" / "favorite_item_pages"
CATALOG = DATA_DIR / "nikke_favorite_items.json"
REPORT = DATA_DIR / "reports" / "favorite_item_skill_refresh_report.json"
BASE_URL = "https://lootandwaifus.com/character/{slug}-nikke/"


def slug_for(name: str) -> str:
    return name.lower().replace(" ", "-").replace(".", "")


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_skills(html: str) -> dict[str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    treasure = soup.select_one(".treasure-alt")
    if treasure is None:
        return {}
    result: dict[str, dict] = {}
    for index, entry in enumerate(treasure.select(".skill-entry"), 1):
        name = entry.select_one("h3")
        description = entry.select("p.level-description")
        if name is None or not description:
            continue
        key = ("skill1", "skill2", "burstSkill")[index - 1] if index <= 3 else f"skill{index}"
        title = name.get_text(" ", strip=True)
        full_text = description[-1].get_text(" ", strip=True)
        skill_type = entry.select_one(".skill-type")
        result[key] = {
            "name": title,
            "type": skill_type.get_text(" ", strip=True) if skill_type else "待确认",
            "effect": full_text,
            "language": "en",
        }
    return result


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    report = {"updated": [], "skipped": [], "failed": [], "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    for item in catalog["items"]:
        if item.get("skills"):
            report["skipped"].append(item["character"])
            continue
        name = item["character"]
        url = BASE_URL.format(slug=slug_for(name))
        try:
            html = fetch(url)
            (CACHE_DIR / f"{slug_for(name)}.html").write_text(html, encoding="utf-8")
            skills = parse_skills(html)
            if len(skills) != 3:
                raise ValueError(f"expected 3 treasure skills, found {len(skills)}")
            item["skills"] = skills
            item["skillSourceUrl"] = url
            report["updated"].append(name)
        except Exception as exc:
            report["failed"].append({"character": name, "url": url, "error": str(exc)})
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
