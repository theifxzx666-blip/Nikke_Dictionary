from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "assets"
EXPORT_DIR = PROJECT_ROOT / "正式产物"
OUT = EXPORT_DIR / "team_liter_crown_cinderella_ein_sanis.png"
TEAM = ["Liter", "Crown", "Cinderella", "Ein", "Anis: Sparkling Summer"]
TITLE = "丽塔 皇冠 灰姑娘 爱因 水阿"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=0)
    return ImageFont.load_default()


F_NAME = font(17)
F_SMALL = font(12)
F_NUM = font(34)
F_ROMAN = font(22)


def rounded_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    outline: tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        pts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return pts


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, fnt: ImageFont.ImageFont) -> str:
    if draw.textlength(text, font=fnt) <= max_width:
        return text
    value = text
    while value and draw.textlength(value + "...", font=fnt) > max_width:
        value = value[:-1]
    return value + "..."


def main() -> None:
    rows = json.loads((DATA_DIR / "nikke_character_dictionary_enhanced.json").read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}

    width, height = 780, 176
    card_width, card_height = 132, 142
    start_x, gap, top = 26, 20, 20

    image = Image.new("RGBA", (width, height), (245, 246, 248, 255))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        shade = 235 + int(12 * y / height)
        draw.line((0, y, width, y), fill=(shade, shade, shade + 2, 255))
    for x in range(0, width, 56):
        draw.line((x, 8, x, height - 8), fill=(205, 207, 210, 150), width=1)

    burst_colors = {"1": (137, 55, 160, 255), "2": (125, 43, 150, 255), "3": (97, 42, 143, 255)}
    element_colors = {
        "Iron": (244, 143, 23, 255),
        "Electric": (178, 26, 220, 255),
        "Fire": (224, 36, 37, 255),
        "Water": (0, 132, 230, 255),
        "Wind": (15, 175, 125, 255),
    }
    class_roman = {"Supporter": "I", "Defender": "II", "Attacker": "III"}

    rounded_rect(draw, (10, 5, 240, 22), 5, (40, 45, 52, 210))
    draw.text((18, 4), TITLE, font=F_SMALL, fill=(255, 255, 255, 255))

    for idx, name in enumerate(TEAM):
        row = by_name[name]
        x = start_x + idx * (card_width + gap)
        y = top

        shadow = Image.new("RGBA", (card_width + 8, card_height + 8), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        rounded_rect(shadow_draw, (4, 4, card_width + 4, card_height + 4), 8, (0, 0, 0, 80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(3))
        image.alpha_composite(shadow, (x - 4, y - 2))
        rounded_rect(draw, (x, y, x + card_width, y + card_height), 7, (255, 255, 255, 255), (95, 95, 95, 255), 2)

        icon_path = ASSET_DIR / "nikke_character_icons" / f"{row['url']}.webp"
        avatar = Image.open(icon_path).convert("RGBA")
        side = min(avatar.size)
        avatar = avatar.crop(
            ((avatar.width - side) // 2, (avatar.height - side) // 2, (avatar.width + side) // 2, (avatar.height + side) // 2)
        ).resize((card_width - 14, card_width - 14), Image.Resampling.LANCZOS)

        element = row.get("element", "")
        accent = element_colors.get(element, (255, 178, 36, 255))
        draw.rectangle((x + 7, y + card_height - 40, x + card_width - 7, y + card_height - 7), fill=accent)
        image.alpha_composite(avatar, (x + 7, y + 18))

        overlay = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.polygon([(0, 0), (card_width * 0.45, 0), (0, card_height * 0.55)], fill=(255, 255, 255, 45))
        image.alpha_composite(overlay, (x, y))

        for star_index in range(3):
            sx = x + 65 + star_index * 16
            sy = y + 14
            draw.polygon(star_points(sx, sy, 8, 3.6), fill=(255, 184, 33, 255), outline=(115, 80, 20, 255))

        burst = str(row.get("burst", ""))
        bx, by = x + card_width - 26, y + 2
        rounded_rect(draw, (bx, by, bx + 27, by + 31), 6, burst_colors.get(burst, (115, 45, 145, 255)), (40, 20, 60, 255), 1)
        draw.text((bx + 6, by + 5), {"1": "01", "2": "02", "3": "03"}.get(burst, burst), font=F_SMALL, fill=(255, 255, 255, 255))

        draw.ellipse((x + 7, y + 7, x + 34, y + 34), fill=(250, 250, 250, 255), outline=(80, 80, 80, 255), width=2)
        draw.text((x + 16, y + 11), "i", font=F_SMALL, fill=(35, 35, 35, 255))
        draw.polygon(
            [(x + 7, y + 40), (x + 32, y + 40), (x + 40, y + 51), (x + 32, y + 62), (x + 7, y + 62), (x + 2, y + 51)],
            fill=(55, 60, 65, 230),
            outline=(245, 245, 245, 255),
        )
        roman = class_roman.get(row.get("class", ""), "?")
        roman_width = draw.textlength(roman, font=F_ROMAN)
        draw.text((x + 20 - roman_width / 2, y + 37), roman, font=F_ROMAN, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))

        draw.text((x + 13, y + card_height - 44), "LV", font=F_SMALL, fill=(255, 230, 105, 255), stroke_width=1, stroke_fill=(50, 50, 50, 255))
        draw.text((x + 8, y + card_height - 34), "415", font=F_NUM, fill=(255, 176, 45, 255), stroke_width=2, stroke_fill=(65, 48, 30, 255))

        element_icon = ASSET_DIR / "nikke_code_icons_gamekee" / f"{element}.png"
        ex, ey = x + card_width - 38, y + card_height - 38
        if element_icon.exists():
            icon = Image.open(element_icon).convert("RGBA").resize((34, 34), Image.Resampling.LANCZOS)
            image.alpha_composite(icon, (ex, ey))
        else:
            draw.regular_polygon((ex + 17, ey + 17, 18), n_sides=6, fill=accent, outline=(30, 30, 30, 255))

        cn_name = fit_text(draw, row.get("cnName", ""), card_width - 18, F_NAME)
        rounded_rect(draw, (x + 7, y + card_height - 64, x + card_width - 7, y + card_height - 42), 4, (20, 24, 28, 160))
        tx = x + card_width / 2 - draw.textlength(cn_name, font=F_NAME) / 2
        draw.text((tx, y + card_height - 64), cn_name, font=F_NAME, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))

    image.convert("RGB").save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
