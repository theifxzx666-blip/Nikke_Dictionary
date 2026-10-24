"""Synchronize dictionary avatars from Nikke.gg as normalized 128x128 PNGs.

GameKee cards and portraits intentionally remain untouched.  This script only
owns ``dotggIconUrl`` and ``localIconFile`` for the dictionary avatar column.
"""

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets" / "nikke_character_icons"
STANDARD_DIR = ASSETS / "standard_128"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
DOTGG_CHARACTERS = DATA / "nikke_characters.json"
REPORT = DATA / "reports" / "dotgg_standard_avatar_sync_report.json"
DOTGG_URL = "https://static.dotgg.gg/nikke/characters/{image}.webp"
DOTGG_BIG_URL = "https://static.dotgg.gg/nikke/characters-big/{image}.webp"
USER_AGENT = "Nikke-Wiki avatar synchronizer/1.0"

# Detail pages verified by the maintainer.  The list snapshot can lag behind
# newly published pages, so these mappings keep independent characters out of
# base-character fallbacks while recording the confirmed source page.
DETAIL_PAGE_OVERRIDES = {
    "方舟黑色游侠": {"slug": "ark-ranger-black", "image": "si_c570_00_s", "avatarImage": "si_c570_00_s"},
    "Prika": {"slug": "prika", "image": "si_c601_00_s", "avatarImage": "si_c601_00_s"},
    "拉普拉斯：究极英雄": {"slug": "laplace-ultimate-hero", "image": "si_c103_00_s", "avatarImage": "si_c103_00_s"},
    "麦斯威尔：平凡技师": {"slug": "maxwell-ordinary-mechanic", "image": "si_c105_00_s", "avatarImage": "si_c105_00_s"},
    # Nikke.gg uses numeric IDs for the transparent character art, while the
    # API's ``img`` value is the actual roster portrait source.
    "gamekee-711739": {"slug": "marciana-marine-study", "image": "322", "avatarImage": "si_c322_00_s"},
    "gamekee-711133": {"slug": "cinderella-crystal-wave", "image": "515", "avatarImage": "si_c515_00_s"},
    "queen-makoto": {"slug": "queen-makoto", "image": "870", "avatarImage": "si_c870_00_s"},
    "yukiko": {"slug": "yukiko", "image": "871", "avatarImage": "si_c871_00_s"},
    "aigis": {"slug": "aigis", "image": "872", "avatarImage": "si_c872_00_s"},
    "gamekee-713891": {"slug": "laplace-ultimate-hero", "image": "", "avatarImage": "si_c103_00_s"},
    "gamekee-713899": {"slug": "maxwell-ordinary-mechanic", "image": "", "avatarImage": "si_c105_00_s"},
}

DERIVED_AVATAR_CROPS = {
    "cinderella-crystal-wave": (250, 0, 720, 390),
    "marciana-marine-study": (130, 0, 700, 400),
    "queen-makoto": (100, 0, 450, 300),
    "yukiko": (100, 0, 500, 300),
    "aigis": (0, 0, 220, 260),
}


def source_path(slug: str) -> Path:
    return ASSETS / f"{slug}.webp"


def typed_source_path(slug: str, kind: str) -> Path:
    return ASSETS / f"{slug}_{kind}.webp"


def is_valid_standard(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.size == (128, 128)
    except (OSError, ValueError):
        return False


def is_valid_avatar_url(url: str) -> bool:
    """Reject numeric character art and full-art URLs in the avatar field."""
    return "/characters/" in url and Path(url.rsplit("/", 1)[-1]).stem.startswith("si_")


def download(url: str, destination: Path) -> bool:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://nikke.gg/characters/"})
        with urllib.request.urlopen(request, timeout=30) as response:
            destination.write_bytes(response.read())
        with Image.open(destination) as image:
            image.verify()
        return True
    except (OSError, ValueError, urllib.error.URLError) as exc:
        destination.unlink(missing_ok=True)
        return False


def normalize(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((128, 128), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((128 - image.width) // 2, (128 - image.height) // 2))
        canvas.save(destination, "PNG", optimize=True)


def derive_avatar(source: Path, destination: Path, crop: tuple[int, int, int, int]) -> None:
    """Create an independent square head/upper-body avatar from full art."""
    with Image.open(source) as image:
        image = image.convert("RGBA").crop(crop)
        bbox = image.getchannel("A").getbbox()
        if bbox:
            image = image.crop(bbox)
        image.thumbnail((128, 128), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((128 - image.width) // 2, (128 - image.height) // 2))
        canvas.save(destination, "PNG", optimize=True)


def main() -> None:
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    dotgg = json.loads(DOTGG_CHARACTERS.read_text(encoding="utf-8"))
    by_name = {item["name"].casefold(): item for item in dotgg if item.get("name")}
    by_slug = {item["url"].casefold(): item for item in dotgg if item.get("url")}
    STANDARD_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "characterTotal": len(rows),
        "matched": [],
        "downloaded": [],
        "normalized": [],
        "derived": [],
        "unmatched": [],
        "failures": [],
    }

    for row in rows:
        name = (row.get("name") or "").strip()
        slug = (row.get("url") or "").strip()
        match = by_name.get(name.casefold()) or by_slug.get(slug.casefold())
        override = DETAIL_PAGE_OVERRIDES.get(name) or DETAIL_PAGE_OVERRIDES.get(slug)
        if override:
            match = {"url": override["slug"], "img": override["image"]}
        if not match:
            # Do not retain a former GameKee 310x402 card as an avatar.
            previous = Path(row.get("localIconFile") or "")
            if not is_valid_standard(previous):
                row["localIconFile"] = ""
            row["avatarStatus"] = "pending_confirmation"
            row["avatarSource"] = "Nikke.gg_unmatched"
            report["unmatched"].append({"name": name, "slug": slug, "reason": "no exact Nikke.gg name/slug match"})
            continue

        dotgg_slug = match["url"]
        image_name = override.get("avatarImage", "") if override else match.get("img", "")
        url_template = DOTGG_URL if override and override.get("avatarImage") else (override.get("urlTemplate", DOTGG_URL) if override else DOTGG_URL)
        url = url_template.format(image=image_name)
        source = typed_source_path(dotgg_slug, "avatar") if override and override.get("avatarImage") else source_path(dotgg_slug)
        if not is_valid_avatar_url(url):
            report["failures"].append({"name": name, "url": url, "reason": "avatar URL is not a roster portrait source"})
            row["localIconFile"] = ""
            row["avatarStatus"] = "pending_confirmation"
            continue
        # The five legacy override files may contain a previously downloaded
        # numeric full-art image, so refresh those small sources once.
        if (override and override.get("avatarImage")) or not source.is_file():
            if download(url, source):
                report["downloaded"].append({"name": name, "file": str(source)})
            else:
                row["localIconFile"] = ""
                row["dotggIconUrl"] = url
                row["avatarStatus"] = "pending_confirmation"
                row["avatarSource"] = "Nikke.gg_detail_page_image_unavailable" if override else "Nikke.gg_download_failed"
                failure = {"name": name, "url": url, "reason": "download or image validation failed"}
                if override:
                    failure["detailPageUrl"] = f"https://nikke.gg/characters/{override['slug']}/"
                report["failures"].append(failure)
                crop = DERIVED_AVATAR_CROPS.get(dotgg_slug)
                portrait_source = source_path(dotgg_slug)
                if crop and portrait_source.is_file():
                    standard = STANDARD_DIR / f"{dotgg_slug}.png"
                    derive_avatar(portrait_source, standard, crop)
                    row["dotggIconUrl"] = ""
                    row["localIconFile"] = str(standard).replace("\\", "/")
                    row["avatarStatus"] = "available_derived"
                    row["avatarSource"] = "Nikke.gg_derived_from_full_art"
                    report["derived"].append({"name": name, "file": str(standard), "source": str(portrait_source)})
                    report["failures"].pop()
                continue

        standard = STANDARD_DIR / f"{dotgg_slug}.png"
        if not is_valid_standard(standard):
            normalize(source, standard)
            report["normalized"].append({"name": name, "file": str(standard)})
        if not is_valid_standard(standard):
            report["failures"].append({"name": name, "file": str(standard), "reason": "normalization validation failed"})
            continue

        row["dotggIconUrl"] = url
        row["localIconFile"] = str(standard).replace("\\", "/")
        row["avatarStatus"] = "available"
        row["avatarSource"] = "Nikke.gg"
        if override and override.get("image"):
            portrait_url = override.get("urlTemplate", DOTGG_BIG_URL).format(image=override["image"])
            # Preserve the previously downloaded large visual under its
            # existing legacy source path when available.
            portrait_source = source_path(dotgg_slug)
            if not portrait_source.is_file() or portrait_source.stat().st_size == 0:
                download(portrait_url, portrait_source)
            if portrait_source.is_file():
                row["dotggPortraitUrl"] = portrait_url
                row["localDotggPortraitFile"] = str(portrait_source).replace("\\", "/")
        report["matched"].append({"name": name, "dotggSlug": dotgg_slug, "localIconFile": row["localIconFile"]})

    DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["matchedCount"] = len(report["matched"])
    report["downloadedCount"] = len(report["downloaded"])
    report["normalizedCount"] = len(report["normalized"])
    report["derivedCount"] = len(report["derived"])
    report["unmatchedCount"] = len(report["unmatched"])
    report["failureCount"] = len(report["failures"])
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("characterTotal", "matchedCount", "downloadedCount", "normalizedCount", "unmatchedCount", "failureCount")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
