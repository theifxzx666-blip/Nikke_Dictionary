import argparse
import json
import math
import os
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "assets"
CHARACTER_JSON = DATA_DIR / "nikke_characters.json"
ICON_DIR = ASSET_DIR / "nikke_character_icons"
INDEX_JSON = DATA_DIR / "nikke_character_icon_index.json"
ALIASES_JSON = DATA_DIR / "nikke_character_aliases.json"


CN_NAMES = {
    "Alice": "爱丽丝",
    "Cinderella": "灰姑娘",
    "Crown": "皇冠",
    "Mast": "马斯特",
    "Red Hood": "小红帽",
    "Liter": "丽塔",
    "Modernia": "神罚",
    "Scarlet": "红莲",
    "Scarlet: Black Shadow": "黑莲",
    "Anis: Sparkling Summer": "水阿",
    "Naga": "娜嘉",
    "Tia": "蒂娅",
    "Dorothy": "桃乐丝",
    "Ein": "爱因",
    "Helm": "海伦",
    "Mast: Romantic Maid": "女仆马斯特",
    "Privaty": "普丽瓦蒂",
    "Privaty: Unkind Maid": "女仆普丽瓦蒂",
    "Rapunzel": "长发公主",
    "Noir": "诺瓦尔",
    "Blanc": "布兰儿",
    "Noise": "诺伊斯",
    "Noah": "诺雅",
    "Centi": "桑迪",
    "Dolla": "朵拉",
    "Rapi": "拉毗",
    "Rapi: Red Hood": "超拉毗",
    "Snow White": "白雪公主",
    "Snow White: Innocent Days": "小白雪",
    "Snow White: Heavy Arms": "重装白雪",
    "Maxwell": "麦斯威尔",
    "Volume": "沃纶姆",
    "Rouge": "胭脂",
    "Biscuit": "饼干",
    "Jackal": "豺狼",
}


def load_aliases() -> dict[str, list[str]]:
    if not ALIASES_JSON.exists():
        return {}
    return json.loads(ALIASES_JSON.read_text(encoding="utf-8"))


def primary_cn_name(name: str) -> str:
    aliases = load_aliases()
    if name in aliases and aliases[name]:
        return aliases[name][0]
    return CN_NAMES.get(name, "")


@dataclass
class Character:
    name: str
    url: str
    img: str
    manufacturer: str
    squad: str
    role: str
    burst: str
    rarity: str
    weapon: str
    element: str

    @property
    def cn_name(self) -> str:
        return primary_cn_name(self.name)


def load_characters() -> list[Character]:
    if not CHARACTER_JSON.exists():
        raise SystemExit(f"Missing {CHARACTER_JSON}. Download https://api.dotgg.gg/nikke/characters first.")
    raw = json.loads(CHARACTER_JSON.read_text(encoding="utf-8"))
    return [
        Character(
            name=x["name"],
            url=x["url"],
            img=x["img"],
            manufacturer=x.get("manufacturer", ""),
            squad=x.get("squad", ""),
            role=x.get("class", ""),
            burst=x.get("burst", ""),
            rarity=x.get("rarity", ""),
            weapon=x.get("weapon", ""),
            element=x.get("element", ""),
        )
        for x in raw
    ]


def download_icons(characters: list[Character]) -> None:
    ICON_DIR.mkdir(exist_ok=True)
    for i, ch in enumerate(characters, 1):
        out = ICON_DIR / f"{ch.url}.webp"
        if out.exists() and out.stat().st_size > 0:
            continue
        url = f"https://static.dotgg.gg/nikke/characters/{ch.img}.webp"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                out.write_bytes(resp.read())
            print(f"[{i}/{len(characters)}] downloaded {ch.name}")
        except Exception as exc:
            print(f"[warn] failed {ch.name}: {exc}", file=sys.stderr)


def portrait_region(img: Image.Image) -> Image.Image:
    """Keep the face/body area and ignore most game UI overlays around card edges."""
    w, h = img.size
    left = int(w * 0.16)
    top = int(h * 0.08)
    right = int(w * 0.84)
    bottom = int(h * 0.76)
    return img.crop((left, top, right, bottom))


def img_feature(img: Image.Image) -> list[float]:
    img = ImageOps.exif_transpose(img.convert("RGB"))
    img = portrait_region(img)
    small = ImageOps.grayscale(img.resize((48, 48), Image.Resampling.LANCZOS))
    arr = np.asarray(small, dtype=np.float32) / 255.0
    arr = (arr - arr.mean()) / (arr.std() + 1e-6)

    rgb = np.asarray(img.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
    hist = []
    for c in range(3):
        h, _ = np.histogram(rgb[:, :, c], bins=16, range=(0.0, 1.0), density=True)
        hist.extend(h.tolist())
    vec = np.concatenate([arr.reshape(-1), np.asarray(hist, dtype=np.float32)])
    norm = np.linalg.norm(vec) + 1e-6
    return (vec / norm).astype(np.float32).tolist()


def build_index(characters: list[Character]) -> None:
    records = []
    for ch in characters:
        path = ICON_DIR / f"{ch.url}.webp"
        if not path.exists():
            continue
        try:
            feature = img_feature(Image.open(path))
        except Exception as exc:
            print(f"[warn] bad icon {path}: {exc}", file=sys.stderr)
            continue
        records.append({"character": ch.__dict__, "feature": feature})
    INDEX_JSON.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    print(f"indexed {len(records)} characters -> {INDEX_JSON}")


def load_index() -> list[dict]:
    if not INDEX_JSON.exists():
        chars = load_characters()
        download_icons(chars)
        build_index(chars)
    return json.loads(INDEX_JSON.read_text(encoding="utf-8"))


def parse_box(text: str) -> tuple[int, int, int, int]:
    nums = [int(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    if len(nums) != 4:
        raise argparse.ArgumentTypeError("box must be x,y,w,h")
    return nums[0], nums[1], nums[2], nums[3]


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def match_crop(img: Image.Image, index: list[dict], topn: int) -> list[dict]:
    feat = np.asarray(img_feature(img), dtype=np.float32)
    aliases = load_aliases()
    scored = []
    for rec in index:
        score = similarity(feat, np.asarray(rec["feature"], dtype=np.float32))
        scored.append((score, rec["character"]))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [
        {
            "score": round(score, 4),
            "name": ch["name"],
            "cnName": primary_cn_name(ch["name"]),
            "aliases": aliases.get(ch["name"], []),
            "burst": ch["burst"],
            "element": ch["element"],
            "class": ch["role"],
            "weapon": ch["weapon"],
            "manufacturer": ch["manufacturer"],
            "url": ch["url"],
        }
        for score, ch in scored[:topn]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="NIKKE character avatar recognizer.")
    parser.add_argument("--setup", action="store_true", help="download icons and rebuild index")
    parser.add_argument("--image", help="screenshot image path")
    parser.add_argument("--team-row", type=parse_box, help="x,y,w,h for a row of 5 character cards")
    parser.add_argument("--crop", action="append", type=parse_box, help="x,y,w,h for one character card; repeatable")
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args()

    chars = load_characters()
    if args.setup:
        download_icons(chars)
        build_index(chars)
        return

    if not args.image:
        parser.error("--image is required unless --setup is used")

    index = load_index()
    shot = Image.open(args.image).convert("RGB")
    crops = []
    if args.team_row:
        x, y, w, h = args.team_row
        card_w = w / 5.0
        for i in range(5):
            crops.append((i + 1, shot.crop((round(x + i * card_w), y, round(x + (i + 1) * card_w), y + h))))
    for i, box in enumerate(args.crop or [], 1):
        x, y, w, h = box
        crops.append((i, shot.crop((x, y, x + w, y + h))))

    if not crops:
        parser.error("provide --team-row or at least one --crop")

    result = []
    for slot, crop in crops:
        result.append({"slot": slot, "matches": match_crop(crop, index, args.top)})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
