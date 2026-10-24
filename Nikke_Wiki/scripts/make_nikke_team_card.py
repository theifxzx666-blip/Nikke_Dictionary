from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "assets"
EXPORT_DIR = PROJECT_ROOT / "正式产物"
OUT = EXPORT_DIR / "team_liter_crown_cinderella_ein_sanis_gamekee.png"
OUT_SIMPLE = EXPORT_DIR / "team_liter_crown_cinderella_ein_sanis_simple.png"
TEAM = ["Liter", "Crown", "Cinderella", "Ein", "Anis: Sparkling Summer"]


PRESET_TEAMS = {
    "liter_crown_cinderella_ein_sanis": {
        "team": ["Liter", "Crown", "Cinderella", "Ein", "Anis: Sparkling Summer"],
        "out": EXPORT_DIR / "team_liter_crown_cinderella_ein_sanis_simple.png",
    },
    "crown_rapi_redhood_redhood_alice_helm": {
        "team": ["Crown", "Rapi: Red Hood", "Red Hood", "Alice", "Helm"],
        "out": EXPORT_DIR / "team_crown_rapi-red-hood_red-hood_alice_helm_simple.png",
    },
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=0)
    return ImageFont.load_default()


F_SMALL = font(12, True)
F_LEVEL = font(30, True)
F_ROMAN = font(21, True)


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def star_points(cx: float, cy: float, outer: float, inner: float):
    return [
        (
            cx + math.cos(-math.pi / 2 + i * math.pi / 5) * (outer if i % 2 == 0 else inner),
            cy + math.sin(-math.pi / 2 + i * math.pi / 5) * (outer if i % 2 == 0 else inner),
        )
        for i in range(10)
    ]


def crop_team_card(path: Path, size: tuple[int, int]) -> Image.Image:
    src = Image.open(path).convert("RGBA")
    target_w, target_h = size
    src_ratio = src.width / src.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)
    img = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    # Keep faces a little high in the frame.
    top = max(0, min(new_h - target_h, int((new_h - target_h) * 0.22)))
    return img.crop((left, top, left + target_w, top + target_h))


def crop_square_icon(path: Path, size: tuple[int, int]) -> Image.Image:
    src = Image.open(path).convert("RGBA")
    side = min(src.width, src.height)
    crop = src.crop(((src.width - side) // 2, (src.height - side) // 2, (src.width + side) // 2, (src.height + side) // 2))
    return crop.resize(size, Image.Resampling.LANCZOS)


def add_icon(image: Image.Image, path_text: str, xy: tuple[int, int], size: tuple[int, int]) -> None:
    if not path_text:
        return
    path = Path(path_text)
    if not path.exists():
        return
    icon = Image.open(path).convert("RGBA")
    icon.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(icon, ((size[0] - icon.width) // 2, (size[1] - icon.height) // 2))
    image.alpha_composite(canvas, xy)


def main() -> None:
    rows = json.loads((DATA_DIR / "nikke_character_dictionary_enhanced.json").read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}

    width, height = 724, 154
    card_w, card_h = 122, 122
    start_x, gap, y = 34, 16, 20

    image = Image.new("RGBA", (width, height), (244, 245, 247, 255))
    draw = ImageDraw.Draw(image)
    for yy in range(height):
        shade = 238 + int(8 * yy / height)
        draw.line((0, yy, width, yy), fill=(shade, shade, shade, 255))
    for x in range(13, width, card_w + gap):
        draw.line((x, 12, x, height - 10), fill=(185, 187, 191, 180), width=1)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(32, 32, 35, 255), width=2)

    burst_colors = {"1": (132, 42, 145, 255), "2": (132, 42, 145, 255), "3": (132, 42, 145, 255)}
    class_roman = {"火力型": "III", "防御型": "II", "辅助型": "I"}
    element_colors = {
        "燃烧": (225, 30, 32, 255),
        "水冷": (0, 132, 230, 255),
        "铁甲": (246, 139, 18, 255),
        "风压": (0, 175, 110, 255),
        "电击": (180, 24, 220, 255),
    }

    for idx, name in enumerate(TEAM):
        row = by_name[name]
        x = start_x + idx * (card_w + gap)

        shadow = Image.new("RGBA", (card_w + 8, card_h + 8), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        rounded(sd, (4, 4, card_w + 4, card_h + 4), 6, (0, 0, 0, 95))
        shadow = shadow.filter(ImageFilter.GaussianBlur(3))
        image.alpha_composite(shadow, (x - 3, y - 2))

        rounded(draw, (x, y, x + card_w, y + card_h), 6, (255, 255, 255, 255), (86, 88, 92, 255), 2)
        icon_path = ASSET_DIR / "nikke_character_icons" / f"{row['url']}.webp"
        if icon_path.exists():
            card = crop_square_icon(icon_path, (card_w - 10, card_h - 10))
        else:
            card = crop_team_card(Path(row["gamekeeLocalTeamCardFile"]), (card_w - 10, card_h - 10))
        image.alpha_composite(card, (x + 5, y + 5))

        overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle((5, card_h - 33, card_w - 5, card_h - 5), fill=(20, 20, 20, 75))
        od.polygon([(5, 5), (54, 5), (5, 58)], fill=(255, 255, 255, 55))
        image.alpha_composite(overlay, (x, y))

        # top-left white circle
        draw.ellipse((x + 6, y + 7, x + 32, y + 33), fill=(248, 248, 248, 255), outline=(65, 65, 65, 255), width=2)
        draw.text((x + 15, y + 10), "i", font=F_SMALL, fill=(25, 25, 25, 255))

        # class badge
        draw.polygon(
            [(x + 4, y + 43), (x + 29, y + 43), (x + 38, y + 54), (x + 29, y + 65), (x + 4, y + 65), (x - 1, y + 54)],
            fill=(47, 52, 58, 238),
            outline=(250, 250, 250, 255),
        )
        roman = class_roman.get(row.get("gamekeeClassCn", ""), "?")
        rw = draw.textlength(roman, font=F_ROMAN)
        draw.text((x + 19 - rw / 2, y + 41), roman, font=F_ROMAN, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))

        # rarity stars
        for s in range(3):
            sx, sy = x + 60 + s * 15, y + 16
            draw.polygon(star_points(sx, sy, 8, 3.8), fill=(255, 181, 35, 255), outline=(105, 73, 20, 255))

        # burst badge
        burst = str(row.get("burst", ""))
        bx, by = x + card_w - 27, y + 2
        rounded(draw, (bx, by, bx + 27, by + 31), 5, burst_colors.get(burst, (132, 42, 145, 255)), (47, 20, 55, 255), 1)
        draw.text((bx + 6, by + 5), {"1": "01", "2": "02", "3": "03"}.get(burst, burst), font=F_SMALL, fill=(255, 255, 255, 255))

        # level
        draw.text((x + 11, y + card_h - 45), "LV", font=F_SMALL, fill=(255, 231, 93, 255), stroke_width=1, stroke_fill=(51, 45, 32, 255))
        draw.text((x + 7, y + card_h - 34), "415", font=F_LEVEL, fill=(255, 171, 42, 255), stroke_width=2, stroke_fill=(55, 43, 30, 255))

        # element icon, with colored backing like the game UI.
        ex, ey = x + card_w - 37, y + card_h - 36
        color = element_colors.get(row.get("gamekeeElementCn", ""), (245, 142, 21, 255))
        draw.regular_polygon((ex + 17, ey + 17, 19), n_sides=6, fill=color, outline=(20, 20, 25, 255))
        add_icon(image, row.get("gamekeeLocalElementIconFile", ""), (ex + 2, ey + 2), (30, 30))

    image.convert("RGB").save(OUT, quality=96)
    print(OUT)


def make_simple(team: list[str] | None = None, out_path: Path | None = None) -> None:
    rows = json.loads((DATA_DIR / "nikke_character_dictionary_enhanced.json").read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}
    team = team or TEAM
    out_path = out_path or OUT_SIMPLE

    width, height = 724, 140
    card_w, card_h = 122, 112
    start_x, gap, y = 34, 16, 14

    image = Image.new("RGBA", (width, height), (244, 245, 247, 255))
    draw = ImageDraw.Draw(image)
    for yy in range(height):
        shade = 239 + int(7 * yy / height)
        draw.line((0, yy, width, yy), fill=(shade, shade, shade, 255))
    for x in range(13, width, card_w + gap):
        draw.line((x, 10, x, height - 9), fill=(188, 190, 194, 180), width=1)
    draw.rectangle((0, 0, width - 1, height - 1), outline=(32, 32, 35, 255), width=2)

    stage_roman = {"一阶": "I", "二阶": "II", "三阶": "III", "通用": "ALL"}
    burst_colors = {"1": (132, 42, 145, 255), "2": (132, 42, 145, 255), "3": (132, 42, 145, 255)}
    element_colors = {
        "燃烧": (225, 30, 32, 255),
        "水冷": (0, 132, 230, 255),
        "铁甲": (246, 139, 18, 255),
        "风压": (0, 175, 110, 255),
        "电击": (180, 24, 220, 255),
    }

    for idx, name in enumerate(team):
        row = by_name[name]
        x = start_x + idx * (card_w + gap)

        shadow = Image.new("RGBA", (card_w + 8, card_h + 8), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        rounded(sd, (4, 4, card_w + 4, card_h + 4), 6, (0, 0, 0, 80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(3))
        image.alpha_composite(shadow, (x - 3, y - 2))

        rounded(draw, (x, y, x + card_w, y + card_h), 6, (255, 255, 255, 255), (86, 88, 92, 255), 2)
        icon_path = ASSET_DIR / "nikke_character_icons" / f"{row['url']}.webp"
        if icon_path.exists():
            card = crop_square_icon(icon_path, (card_w - 10, card_h - 10))
        else:
            card = crop_team_card(Path(row["gamekeeLocalTeamCardFile"]), (card_w - 10, card_h - 10))
        image.alpha_composite(card, (x + 5, y + 5))

        overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.polygon([(5, 5), (54, 5), (5, 58)], fill=(255, 255, 255, 50))
        image.alpha_composite(overlay, (x, y))

        # Left-top: weapon type.
        draw.ellipse((x + 6, y + 6, x + 34, y + 34), fill=(248, 248, 248, 245), outline=(64, 64, 64, 255), width=2)
        add_icon(image, row.get("gamekeeLocalWeaponIconFile", ""), (x + 9, y + 9), (22, 22))

        # Left badge: burst stage in Roman numerals.
        roman = stage_roman.get(row.get("gamekeeStageCn", ""), "?")
        draw.polygon(
            [(x + 4, y + 43), (x + 31, y + 43), (x + 40, y + 54), (x + 31, y + 65), (x + 4, y + 65), (x - 1, y + 54)],
            fill=(47, 52, 58, 238),
            outline=(250, 250, 250, 255),
        )
        rw = draw.textlength(roman, font=F_ROMAN)
        draw.text((x + 20 - rw / 2, y + 41), roman, font=F_ROMAN, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))

        # Top-right: in-game burst number, kept compact for ordering context.
        burst = str(row.get("burst", ""))
        bx, by = x + card_w - 27, y + 2
        rounded(draw, (bx, by, bx + 27, by + 31), 5, burst_colors.get(burst, (132, 42, 145, 255)), (47, 20, 55, 255), 1)
        draw.text((bx + 4, by + 5), {"1": "01", "2": "02", "3": "03", "p": "ALL"}.get(burst, burst), font=F_SMALL, fill=(255, 255, 255, 255))

        # Bottom-right: element.
        ex, ey = x + card_w - 37, y + card_h - 36
        color = element_colors.get(row.get("gamekeeElementCn", ""), (245, 142, 21, 255))
        draw.regular_polygon((ex + 17, ey + 17, 19), n_sides=6, fill=color, outline=(20, 20, 25, 255))
        add_icon(image, row.get("gamekeeLocalElementIconFile", ""), (ex + 2, ey + 2), (30, 30))

    image.convert("RGB").save(out_path, quality=96)
    print(out_path)


if __name__ == "__main__":
    import sys

    key = sys.argv[1] if len(sys.argv) > 1 else "liter_crown_cinderella_ein_sanis"
    preset = PRESET_TEAMS.get(key)
    if preset:
        make_simple(preset["team"], preset["out"])
    else:
        make_simple()
