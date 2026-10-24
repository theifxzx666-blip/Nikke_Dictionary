# -*- coding: utf-8 -*-
"""重构角色辞典：文本取 Wiki，图片优先拆包素材库，缺图才回落 Wiki 缓存图。

设计口径
--------
- 身份/战斗/技能/国服状态：沿用 `data/nikke_character_dictionary_enhanced.json`
  （元数据来自 Nikke.gg，技能文本来自 GameKee 加点页 Lv10 快照）。
- 图片：**优先** `00_资源库/01_角色` 两档（头像 / 立绘HD）；
  素材库确实没有的，才回落到此前从 Wiki 抓下来的本地图（character_repository）；
  两者都没有则记 missing，并留下 remoteFallback 远程地址供后续补。
- SD立绘（`01_角色/SD立绘/`）不收：那是战斗小人的逐帧拆图，对辞典/卡片无使用价值。
- 代号归一：素材库同一角色在不同子目录里写作 `c10_00` 或 `c010_00`，
  词典里还混入过把文件名当代号存的情况（如 `拉普拉斯：究极英雄_c103_00.png`），
  统一用正则抽出 (base, variant) 数字对做匹配键。

用法
----
    python scripts/build_character_codex.py --dry-run
    python scripts/build_character_codex.py --apply
    python scripts/build_character_codex.py --apply --no-images   # 不嵌入缩略图，出表更快
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl.drawing.image import Image as XlsxImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICT_JSON = PROJECT_ROOT / "data" / "nikke_character_dictionary_enhanced.json"
CN_STATUS_JSON = PROJECT_ROOT / "data" / "cn_release_status.json"
LIBRARY_ROOT = Path(r"F:\Codex\Nikke\Nikke_Skills\拆包\00_资源库")
CHAR_ROOT = LIBRARY_ROOT / "01_角色"
WIKI_ROOT = PROJECT_ROOT / "data" / "character_repository" / "assets" / "official"
# 本地角色看图缓存（Wiki 抓取的按 slug 归档）：含 portrait.webp(256×512 半身) / avatar.png /
# nikke_gg_portrait.webp(高清) / team_card.png，优先于 128 方图标使用
CACHE_ROOT = PROJECT_ROOT / "data" / "character_repository" / "assets" / "characters"
ICON_ROOT = PROJECT_ROOT / "assets" / "nikke_character_icons" / "standard_128"

OUT_DIR = PROJECT_ROOT / "正式产物"
OUT_JSON = OUT_DIR / "角色辞典.json"
OUT_XLSX = OUT_DIR / "角色辞典.xlsx"
REPORT_DIR = PROJECT_ROOT / "核心目录" / "报告"
TMP_DIR = PROJECT_ROOT / "assets" / ".codex_thumbs"

CODE_RE = re.compile(r"c0*(\d+)_0*(\d+)")
# 素材库三档，口径对齐客户端真实用途（见 00_索引/素材场景说明.md）：
#   icon     = `立绘SI/ si_cXXX_YY_s`     128×128 官方方形头像（列表缩略 / UI 占位）
#   avatar   = `头像/   *_mi_uc_tex`       256×512 半身像（队伍编成队员卡 / 妮姬列表 / 名片）
#   portrait = `立绘HD/ *_uc_tex`          1024²/2048² 立绘（详情 → 立绘鉴赏）
# 注意：同一档存在国际服变体（`..._mi_uc_tex_intl.png` / `..._uc_tex_intl.png`），
# 优先取非 intl 版本，缺了再用 intl 补。
KINDS = (
    ("icon", "头像", "立绘SI", "si_c"),
    ("avatar", "半身像", "头像", "_mi_uc_tex"),
    ("portrait", "立绘", "立绘HD", "_uc_tex"),
)
# 不参与「文件名中文名反查」的档：SI 文件名是 `si_c331_00_s_xxx.png`，没有中文名
NAME_INDEX_SKIP = {"icon"}
FALLBACK_NOTE = {
    "library": "拆包素材库",
    "cache": "本地缓存半身像",
    "derived": "从全身图裁切",
    "wiki": "Wiki小图标(128)",
    "missing": "未获取",
}
STATUS_KEYS = ("library", "cache", "derived", "wiki", "missing")
DERIVED_DIR = PROJECT_ROOT / "assets" / ".codex_busts"


def code_key(text: str) -> str | None:
    """把任意写法/污染写法的代号归一成匹配键：'c172_0'。"""
    m = None
    for m in CODE_RE.finditer(str(text or "")):
        pass
    return f"c{int(m.group(1))}_{int(m.group(2))}" if m else None


def display_code(text: str) -> str | None:
    m = None
    for m in CODE_RE.finditer(str(text or "")):
        pass
    return f"c{int(m.group(1)):03d}_{int(m.group(2)):02d}" if m else None


def load_dictionary() -> list[dict]:
    with DICT_JSON.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def index_library() -> dict[str, dict[str, Path]]:
    """返回 {代号键: {内部键: 路径}}。

    同档多份文件时优先非国际服版（不带 `_intl`），其次才用 intl 版补齐。
    """
    idx: dict[str, dict[str, Path]] = defaultdict(dict)
    dup: Counter[str] = Counter()
    for key, _label, subdir, marker in KINDS:
        root = CHAR_ROOT / subdir
        if not root.is_dir():
            continue
        # 排序：非 intl 在前
        entries = sorted(
            root.iterdir(),
            key=lambda p: ("_intl" in p.name, len(p.name), p.name),
        )
        for entry in entries:
            if not entry.is_file() or not entry.name.endswith(".png"):
                continue
            if marker not in entry.name:
                continue
            ck = code_key(entry.name)
            if not ck:
                continue
            if key in idx[ck]:
                dup[f"{subdir}/{ck}"] += 1
                continue
            idx[ck][key] = entry
    if dup:
        print(f"  · 同一代号多份文件（已按非 intl 优先取一份）：{len(dup)} 组")
    return idx


def base_index(lib: dict[str, dict[str, Path]]) -> dict[str, list[str]]:
    """按基础代号（不含变体）反查所有已有代号键，用于变体近似匹配。"""
    out: dict[str, list[str]] = defaultdict(list)
    for ck in lib:
        out[ck.split("_")[0]].append(ck)
    for keys in out.values():
        keys.sort(key=lambda k: (int(k.split("_")[1]), k))
    return out


def lookup(lib, by_base, ck: str | None, kind: str) -> tuple[Path | None, bool]:
    """先精确匹配 (代号+变体)，再退到同基础代号的其他变体。

    返回 (路径, 是否为变体近似)。近似用于「词典记 c103_00、素材库只有 c103_01」这类情况。
    """
    if not ck:
        return None, False
    exact = lib.get(ck, {}).get(kind)
    if exact:
        return exact, False
    for alt in by_base.get(ck.split("_")[0], []):
        if alt == ck:
            continue
        cand = lib.get(alt, {}).get(kind)
        if cand:
            return cand, True
    return None, False


def rel_to_library(path: Path) -> str:
    try:
        return path.relative_to(LIBRARY_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# ---- 代号解析：双通道 -------------------------------------------------------
# 词典里有部分记录没有 officialCode / iconId（GameKee 独有条目），但代号仍可从两处拿到：
#   ① dotggIconUrl 里内嵌客户端代号，如 `.../si_c570_00_s.webp`
#   ② 素材库文件名带中文名，如 `方舟黑色游侠_c570_00_mi_uc_tex_intl.png`
# 两通道都试，取到即用；仍取不到才算「无代号」。

DOTGG_CODE_RE = re.compile(r"si_(c\d+_\d+)_")


def library_name_index() -> dict[str, str]:
    """素材库文件名 → {中文名: 代号键}，用于无代号记录按名字反查。

    SI 档（`si_c331_00_s_*.png`）文件名里没有中文名，跳过；其余两档文件名形如
    `钟鸣_c331_00_uc_tex.png`，取 `_c` 前缀即中文名。
    """
    idx: dict[str, str] = {}
    for key, _label, subdir, marker in KINDS:
        if key in NAME_INDEX_SKIP:
            continue
        root = CHAR_ROOT / subdir
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: ("_intl" in p.name, p.name)):
            if not entry.is_file() or not entry.name.endswith(".png"):
                continue
            if marker not in entry.name:
                continue
            ck = code_key(entry.name)
            if not ck:
                continue
            name = entry.name.split("_c", 1)[0].strip()
            if name and name not in idx:
                idx[name] = ck
    return idx


def resolve_code(rec: dict, name_idx: dict[str, str] | None = None) -> tuple[str | None, str]:
    """返回 (代号键, 来源)，来源取值 officialCode / iconId / dotggIconUrl / libraryName。"""
    for field, source in (("officialCode", "officialCode"), ("iconId", "iconId")):
        ck = code_key(rec.get(field) or "")
        if ck:
            return ck, source
    m = DOTGG_CODE_RE.search(str(rec.get("dotggIconUrl") or ""))
    if m:
        return code_key(m.group(1)), "dotggIconUrl"
    if name_idx:
        cn = str(rec.get("cnName") or rec.get("name") or "").strip()
        if cn in name_idx:
            return name_idx[cn], "libraryName"
    return None, ""


def crop_bust(source: Path, dest: Path, size: tuple[int, int] = (256, 512)) -> Path | None:
    """从全身/方图裁出半身像：取内容顶部 40% 高度、按 1:2 画幅横向对准头部。

    头部横向定位用「最顶部 12% 窄条」的 alpha 包围盒中心——整块上部区域算重心会被
    背包/武器/披风带偏（钟鸣曾因此把画面裁到一把剑上）。

    仅在「素材库无半身像档、本地缓存也无现成半身像」时兜底使用。
    """
    try:
        with Image.open(source) as im:
            im = im.convert("RGBA")
            box = im.getbbox()
            if not box:
                return None
            left, top, right, bottom = box
            content_h = bottom - top
            win_h = max(1, int(content_h * 0.40))
            win_w = max(1, int(win_h * size[1] / size[0]))
            # 头部横向位置：只取最顶部窄条，避免躯干/道具拉偏重心
            strip_h = max(8, int(content_h * 0.12))
            strip = im.crop((left, top, right, top + strip_h))
            alpha = strip.getchannel("A")
            bbox_head = alpha.getbbox() or (left, 0, right, strip_h)
            cx = (bbox_head[0] + bbox_head[2]) // 2
            x0 = min(max(cx - win_w // 2, left), max(left, right - win_w))
            crop = im.crop((x0, top, x0 + win_w, top + win_h))
            dest.parent.mkdir(parents=True, exist_ok=True)
            crop.resize(size, Image.Resampling.LANCZOS).save(dest)
            return dest
    except Exception:
        return None


def image_meta(path: Path) -> dict:
    info = {"path": path.as_posix(), "sizeKB": round(path.stat().st_size / 1024, 1)}
    try:
        with Image.open(path) as im:
            info["width"], info["height"] = im.size
    except Exception:
        info["width"] = info["height"] = None
    return info


def resolve_assets(
    rec: dict,
    lib: dict[str, dict[str, Path]],
    by_base: dict[str, list[str]] | None = None,
    name_idx: dict[str, str] | None = None,
) -> tuple[dict, dict]:
    """解析两档素材（头像 / 立绘），返回 (assets, 统计)。"""
    ck, _code_source = resolve_code(rec, name_idx)
    slug = str(rec.get("url") or "")
    by_base = by_base if by_base is not None else base_index(lib)

    assets: dict[str, dict] = {}
    stats: dict[str, str] = {}

    def library_entry(kind: str) -> dict | None:
        path, approx = lookup(lib, by_base, ck, kind)
        if not path:
            return None
        entry = {"status": "library", **image_meta(path)}
        entry["relPath"] = rel_to_library(path)
        if approx:
            entry["approximate"] = True      # 变体近似：素材库里没有该变体，用同角色其他变体
        return entry

    # ---- 图标：素材库 SI 方图 → 从半身像裁方 → Wiki 128 小图标 → missing ----
    icon = library_entry("icon")
    if icon is None:
        bust_src = library_entry("avatar")
        if bust_src:
            square = thumb_for(bust_src["path"], f"{slug or 'x'}_icon", 256)
            if square:
                icon = {"status": "derived", **image_meta(square), "derivedFrom": bust_src["path"],
                        "note": "从半身像裁头顶方图"}
        if icon is None:
            cand = next(
                (ICON_ROOT / f"{slug}{ext}" for ext in (".png", ".PNG") if (ICON_ROOT / f"{slug}{ext}").is_file()),
                None,
            )
            icon = {"status": "wiki", **image_meta(cand)} if cand else {"status": "missing"}
    icon["remoteFallback"] = rec.get("dotggIconUrl") or ""
    assets["icon"] = icon
    stats["icon"] = icon["status"]

    # 头像（半身像）兜底链：素材库 → 本地缓存半身像 → 从立绘裁切 → missing
    entry = library_entry("avatar")
    if entry is None:
        # ① 本地缓存里现成的半身像（portrait.webp 通常就是 256×512）
        cand = CACHE_ROOT / slug / "portrait.webp"
        if cand.is_file():
            with Image.open(cand) as im:
                w, h = im.size
            if abs(w / h - 0.5) < 0.06:            # 本来就接近 1:2，直接用
                entry = {"status": "cache", **image_meta(cand)}
            else:
                entry = None
            cache_src = cand
        else:
            cache_src = None
        # ② 仍没有，就从立绘裁一张半身像：素材库 HD 立绘优先（客户端原生），再退本地缓存全身图
        if entry is None:
            lib_portrait = library_entry("portrait")
            full = next(
                (
                    p
                    for p in (
                        Path(lib_portrait["path"]) if lib_portrait else None,
                        CACHE_ROOT / slug / "nikke_gg_portrait.webp",
                        WIKI_ROOT / slug / "hd.png",
                        WIKI_ROOT / slug / "fullbody.png",
                    )
                    if p is not None and p.is_file()
                ),
                None,
            )
            bust = crop_bust(full, DERIVED_DIR / f"{slug}.png") if full else None
            if bust:
                entry = {"status": "derived", **image_meta(bust), "derivedFrom": full.as_posix()}
            elif cache_src is not None:
                entry = {"status": "cache", **image_meta(cache_src)}
        # ③ 最后才用 128 方图标
        if entry is None:
            icon = next((ICON_ROOT / f"{slug}{ext}" for ext in (".png", ".PNG") if (ICON_ROOT / f"{slug}{ext}").is_file()), None)
            if icon is None:
                icon = next((p for p in (WIKI_ROOT / slug / "portrait.png",) if p.is_file()), None)
            entry = {"status": "wiki", **image_meta(icon)} if icon else {"status": "missing"}
    entry["remoteFallback"] = rec.get("dotggIconUrl") or rec.get("gamekeeIconUrl") or ""
    assets["avatar"] = entry
    stats["avatar"] = entry["status"]

    # 立绘：素材库立绘HD → 本地缓存高清 → Wiki 缓存全身图
    entry = library_entry("portrait")
    if entry is None:
        cand = next(
            (
                p
                for p in (
                    CACHE_ROOT / slug / "nikke_gg_portrait.webp",
                    CACHE_ROOT / slug / "portrait.webp",
                    WIKI_ROOT / slug / "fullbody.png",
                    WIKI_ROOT / slug / "hd.png",
                )
                if p.is_file()
            ),
            None,
        )
        if cand:
            status = "cache" if CACHE_ROOT in cand.parents else "wiki"
            entry = {"status": status, **image_meta(cand)}
        else:
            entry = {"status": "missing"}
    entry["remoteFallback"] = rec.get("gamekeePortraitUrl") or rec.get("dotggIconUrl") or ""
    assets["portrait"] = entry
    stats["portrait"] = entry["status"]
    return assets, stats


def build_record(rec: dict, assets: dict, code: str | None = None, code_source: str = "") -> dict:
    def as_dict(value):
        return value if isinstance(value, dict) else {}

    evidence = as_dict(rec.get("cnClientEvidence"))
    skills = {}
    for slot, label in (("skill1", "技能1"), ("skill2", "技能2"), ("burstSkill", "爆裂技能")):
        block = as_dict(as_dict(rec.get("skills")).get(slot))
        if not block:
            continue
        skills[slot] = {
            "label": label,
            "name": block.get("name") or "",
            "type": block.get("type") or "",
            "cooldown": block.get("cooldown") or "",
            "effect": block.get("effect") or "",          # 已是 Lv10 面板
            "levels": block.get("levels") or {},
            "iconUrl": block.get("iconUrl") or "",
        }

    combat = {
        "manufacturer": rec.get("manufacturer") or "",
        "manufacturerCn": rec.get("gamekeeCompanyCn") or "",
        "squad": rec.get("squad") or "",
        "squadCn": rec.get("gamekeeSquadCn") or "",
        "class": rec.get("class") or "",
        "classCn": rec.get("gamekeeClassCn") or "",
        "burst": rec.get("burst") or "",
        "burstCn": rec.get("gamekeeStageCn") or "",
        "element": rec.get("element") or "",
        "elementCn": rec.get("gamekeeElementCn") or "",
        "weapon": rec.get("weapon") or "",
        "weaponCn": rec.get("gamekeeWeaponCn") or rec.get("weaponNameCn") or "",
        "rarity": rec.get("rarity") or "",
        "burstGen": rec.get("burstGen") or "",
    }

    return {
        "slug": rec.get("url") or "",
        "clientCode": display_code(code or "") or "",
        "clientCodeSource": code_source,
        "identity": {
            "cnName": rec.get("cnName") or "",
            "englishName": rec.get("name") or "",
            "aliases": [a for a in str(rec.get("aliases") or "").split("|") if a.strip()],
            "iconId": rec.get("iconId") or "",
        },
        "combat": combat,
        "skills": skills,
        "normalAttack": as_dict(rec.get("normalAttack")),
        "treasure": as_dict(rec.get("favoriteItem")) or None,
        "costumes": rec.get("costumes") or [],
        "availability": {
            "cnReleased": rec.get("cnReleased") or "",
            "basis": rec.get("releaseBasis") or "",
            "clientCharId": evidence.get("charId"),
            "clientTier": evidence.get("tier") or "",
        },
        "assets": assets,
        "sources": {
            "nikkeGg": {"slug": rec.get("url") or "", "iconUrl": rec.get("dotggIconUrl") or ""},
            "gamekee": {
                "contentId": rec.get("gamekeeContentId") or "",
                "entryId": rec.get("gamekeeEntryId") or "",
                "portraitUrl": rec.get("gamekeePortraitUrl") or "",
            },
        },
    }


def summarize(records: list[dict]) -> dict:
    counts = {}
    for key in ("icon", "avatar", "portrait"):
        c = Counter(r["assets"][key]["status"] for r in records)
        counts[key] = {k: c.get(k, 0) for k in STATUS_KEYS}
    counts["characters"] = len(records)
    counts["cnReleased"] = sum(1 for r in records if r["availability"]["cnReleased"] == "已上线")
    counts["withSkills"] = sum(1 for r in records if len(r["skills"]) >= 3)
    counts["noCode"] = sum(1 for r in records if not r["clientCode"])
    return counts


def write_json(payload: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUT_JSON.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(OUT_JSON)


def thumb_for(path: str, name: str, size: int = 80) -> Path | None:
    """生成方形缩略图。

    - 源本身接近正方形（SI 官方头像 128×128，含少量 117~128 紧裁切）：整图按长边等比缩放后居中贴片，不裁内容。
    - 源是 1:2 半身像 / 全身图：取内容顶部正方形（头部+肩），避免竖图塞进方格后变成窄条。
    """
    src = Path(path)
    if not src.is_file():
        return None
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out = TMP_DIR / f"{name}_{size}.png"
    try:
        with Image.open(src) as im:
            im = im.convert("RGBA")
            box = im.getbbox() or (0, 0, im.width, im.height)
            bw, bh = box[2] - box[0], box[3] - box[1]
            if 0.85 <= bw / bh <= 1.18:
                crop = im.crop(box)
            else:
                side = min(bw, bh)
                top = box[1]
                if top + side > im.height:
                    top = max(0, im.height - side)
                left = max(0, min(box[0] + (bw - side) // 2, im.width - side))
                crop = im.crop((left, top, left + side, top + side))
            canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
            fitted = crop.copy()
            fitted.thumbnail((size, size), Image.Resampling.LANCZOS)
            canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2), fitted)
            canvas.save(out)
    except Exception:
        return None
    return out


HEAD_FILL = PatternFill("solid", fgColor="2F5597")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=10)


def style_sheet(ws, widths: list[int], freeze: str = "A2") -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for cell in ws[1]:
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = freeze


def write_xlsx(payload: dict, with_images: bool = True) -> None:
    records = payload["characters"]
    wb = openpyxl.Workbook()

    # ---- 角色总表 ----
    ws = wb.active
    ws.title = "角色总表"
    header = [
        "头像", "中文名", "英文名", "别名", "客户端代号", "企业", "部队", "职业",
        "爆裂", "属性", "武器", "稀有度", "爆裂值", "国服状态", "头像来源", "立绘来源",
    ]
    ws.append(header)
    for i, r in enumerate(records, start=2):
        a = r["assets"]
        ws.append([
            "",
            r["identity"]["cnName"],
            r["identity"]["englishName"],
            "／".join(r["identity"]["aliases"][:6]),
            r["clientCode"],
            r["combat"]["manufacturerCn"] or r["combat"]["manufacturer"],
            r["combat"]["squadCn"] or r["combat"]["squad"],
            r["combat"]["classCn"] or r["combat"]["class"],
            r["combat"]["burstCn"] or r["combat"]["burst"],
            r["combat"]["elementCn"] or r["combat"]["element"],
            r["combat"]["weaponCn"] or r["combat"]["weapon"],
            r["combat"]["rarity"],
            r["combat"]["burstGen"],
            r["availability"]["cnReleased"],
            FALLBACK_NOTE[a["icon"]["status"]],
            FALLBACK_NOTE[a["portrait"]["status"]],
        ])
        if with_images:
            src = a["icon"].get("path") or a["avatar"].get("path") or a["portrait"].get("path")
            if src:
                thumb = thumb_for(src, r["slug"] or f"row{i}")
                if thumb:
                    img = XlsxImage(str(thumb))
                    img.width = img.height = 80          # px，跨 80 内部宽，列宽已放宽到 12
                    ws.add_image(img, f"A{i}")
        ws.row_dimensions[i].height = 60                  # 60pt = 80px，与图片等高，不跨行
    style_sheet(ws, [12, 14, 18, 26, 12, 12, 14, 12, 8, 8, 12, 8, 9, 12, 14, 14])

    # ---- 技能明细 ----
    ws2 = wb.create_sheet("技能明细")
    ws2.append(["中文名", "英文名", "栏位", "技能名", "类型", "冷却", "效果（Lv10）"])
    for r in records:
        for slot in ("skill1", "skill2", "burstSkill"):
            s = r["skills"].get(slot)
            if not s:
                continue
            ws2.append([
                r["identity"]["cnName"], r["identity"]["englishName"], s["label"],
                s["name"], s["type"], s["cooldown"], (s["effect"] or "").replace("\n", " "),
            ])
    style_sheet(ws2, [14, 18, 10, 18, 8, 8, 90])
    for row in ws2.iter_rows(min_row=2):
        row[6].alignment = Alignment(wrap_text=True, vertical="top")

    # ---- 普攻明细 ----
    ws3 = wb.create_sheet("普攻明细")
    ws3.append(["中文名", "英文名", "武器类型", "弹匣", "描述"])
    for r in records:
        na = r["normalAttack"] or {}
        if not na:
            continue
        ws3.append([
            r["identity"]["cnName"], r["identity"]["englishName"],
            na.get("type") or "", na.get("ammo") or "", (na.get("desc") or "").replace("\n", " "),
        ])
    style_sheet(ws3, [14, 18, 12, 8, 90])
    for row in ws3.iter_rows(min_row=2):
        row[4].alignment = Alignment(wrap_text=True, vertical="top")

    # ---- 素材清单 ----
    ws4 = wb.create_sheet("素材清单")
    ws4.append([
        "中文名", "英文名", "代号", "头像 SI（素材库相对路径）", "头像来源",
        "半身像（素材库相对路径）", "半身像来源",
        "立绘 HD（素材库相对路径）", "立绘来源", "远程兜底",
    ])
    for r in records:
        a = r["assets"]
        ws4.append([
            r["identity"]["cnName"], r["identity"]["englishName"], r["clientCode"],
            a["icon"].get("relPath") or a["icon"].get("path") or "",
            FALLBACK_NOTE[a["icon"]["status"]],
            a["avatar"].get("relPath") or a["avatar"].get("path") or "",
            FALLBACK_NOTE[a["avatar"]["status"]],
            a["portrait"].get("relPath") or a["portrait"].get("path") or "",
            FALLBACK_NOTE[a["portrait"]["status"]],
            a["portrait"].get("remoteFallback") or "",
        ])
    style_sheet(ws4, [14, 18, 10, 46, 14, 46, 14, 46, 12, 40])

    # ---- 兜底来源 ----
    ws5 = wb.create_sheet("兜底来源")
    ws5.append(["中文名", "英文名", "代号", "档位", "实际来源", "远程兜底地址"])
    for r in records:
        for key, label in (("icon", "头像"), ("avatar", "半身像"), ("portrait", "立绘")):
            st = r["assets"][key]
            if st["status"] == "library":
                continue
            ws5.append([
                r["identity"]["cnName"], r["identity"]["englishName"], r["clientCode"],
                label, FALLBACK_NOTE[st["status"]],
                st.get("remoteFallback") or "",
            ])
    style_sheet(ws5, [14, 18, 12, 10, 14, 46])

    # ---- 说明 ----
    ws6 = wb.create_sheet("说明")
    c = payload["counts"]
    lines = [
        ("角色辞典（重构版）", ""),
        ("生成时间", payload["generatedAt"]),
        ("角色数", c["characters"]),
        ("头像 SI·拆包素材库", c["icon"]["library"]),
        ("头像 SI·从半身像裁切", c["icon"]["derived"]),
        ("头像 SI·Wiki小图标(128)", c["icon"]["wiki"]),
        ("半身像·拆包素材库", c["avatar"]["library"]),
        ("半身像·本地缓存", c["avatar"]["cache"]),
        ("半身像·从立绘裁切", c["avatar"]["derived"]),
        ("立绘 HD·拆包素材库", c["portrait"]["library"]),
        ("立绘 HD·本地缓存", c["portrait"]["cache"]),
        ("图片口径", "客户端三档：头像=立绘SI(128² 官方方图) → 半身像=头像/*_mi_uc_tex(256×512) → 立绘=立绘HD(1024²/2048²)；缺档才裁切或回落 Wiki 缓存"),
        ("文本口径", "身份/战斗/Nikke.gg；技能与普攻文本 GameKee 加点页 Lv10 快照"),
        ("素材库根目录", payload["libraryRoot"]),
        ("词典型式", "角色辞典.json（本表为其可视化副本）"),
    ]
    for row in lines:
        ws6.append(list(row))
    ws6.column_dimensions["A"].width = 22
    ws6.column_dimensions["B"].width = 96
    ws6["A1"].font = Font(bold=True, size=14)

    if payload.get("clientAudit"):
        write_roster_sheet(wb, payload["clientAudit"])

    tmp = OUT_XLSX.with_name(OUT_XLSX.stem + ".tmp.xlsx")
    wb.save(tmp)
    tmp.replace(OUT_XLSX)


def audit_roster(records: list[dict], lib: dict[str, dict[str, Path]]) -> list[dict]:
    """客户端对账：素材库全量代号 vs 国服 locale 名单 vs 辞典已收条目。

    判据只有两条硬证据——
    ① 国服客户端 locale（`data/cn_release_status.json` 的 `客户端 id=`）
    ② 素材库是否真有该代号的立绘/方图
    不做「看着像可玩角色就收」的推断。
    """
    status = json.loads(CN_STATUS_JSON.read_text(encoding="utf-8-sig"))
    locale: dict[int, str] = {}
    for name, item in status.items():
        if name == "_schema" or not isinstance(item, dict):
            continue
        m = re.search(r"id=(\d+)", str(item.get("note") or ""))
        if m:
            locale[int(m.group(1))] = str(item.get("status") or "")

    codex_ids = {int(r["clientCode"].split("_")[0][1:]) for r in records if r["clientCode"]}

    by_id: dict[int, dict] = {}
    for ck, kinds in lib.items():
        head, variant = ck.split("_")
        base_id, variant = int(head[1:]), int(variant)
        row = by_id.setdefault(base_id, {"kinds": set(), "names": set(), "variants": set()})
        row["kinds"].update(kinds)
        row["variants"].add(variant)
        for kind, path in kinds.items():
            if kind in NAME_INDEX_SKIP:
                continue
            # 只有 `<中文名>_c<id>_<变体>_...` 这种命名才带中文名；
            # `c063_00_uc_tex_intl.png` 这类纯代号文件名不含 `_c` 分隔，不算名。
            stem = path.name
            nm = stem.split("_c", 1)[0].strip() if "_c" in stem else ""
            if nm and not re.fullmatch(r"c\d+", nm):
                row["names"].add(nm)

    out = []
    for cid in sorted(by_id):
        info = by_id[cid]
        in_locale = cid in locale
        in_codex = cid in codex_ids
        if in_codex:
            cat = "已入典"
        elif in_locale:
            cat = "国服有记录·辞典未收"
        elif info["names"]:
            cat = "客户端独有·有名"
        else:
            cat = "客户端独有·无名(NPC池)"
        out.append({
            "clientId": cid,
            "code": f"c{cid:03d}_{min(info['variants']):02d}",
            "libraryName": "／".join(sorted(info["names"])) or "",
            "icon": "icon" in info["kinds"],
            "avatar": "avatar" in info["kinds"],
            "portrait": "portrait" in info["kinds"],
            "variants": len(info["variants"]),
            "locale": locale.get(cid, ""),
            "category": cat,
            "inCodex": in_codex,
        })
    return out


def write_roster_sheet(wb, audit: list[dict]) -> None:
    ws = wb.create_sheet("客户端对账")
    ws.append(["客户端 id", "代号", "素材库中文名", "SI方图", "半身像", "立绘HD", "变体数",
               "国服locale", "分类", "辞典是否已收"])
    for a in audit:
        ws.append([
            a["clientId"], a["code"], a["libraryName"] or "—",
            "有" if a["icon"] else "—",
            "有" if a["avatar"] else "—",
            "有" if a["portrait"] else "—",
            a["variants"], a["locale"] or "无记录", a["category"],
            "是" if a["inCodex"] else "否",
        ])
    style_sheet(ws, [10, 12, 20, 8, 8, 8, 8, 12, 22, 12])

    counter = Counter(a["category"] for a in audit)
    ws_note = wb["说明"]
    ws_note.append([])
    ws_note.append(["客户端对账", "素材库全量代号 vs 国服 locale vs 辞典；明细见「客户端对账」表"])
    for cat in ("已入典", "国服有记录·辞典未收", "客户端独有·有名", "客户端独有·无名(NPC池)"):
        ws_note.append([f"　{cat}", counter.get(cat, 0)])
    ws_note.append(["　客户端代号合计", len(audit)])


def write_report(payload: dict, records: list[dict]) -> Path:
    c = payload["counts"]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"角色辞典重构_{datetime.now():%Y%m%d}.md"
    lines = [
        f"# 角色辞典重构报告（{datetime.now():%Y-%m-%d %H:%M}）",
        "",
        "## 1. 口径",
        "",
        "| 维度 | 来源 |",
        "|---|---|",
        "| 身份/战斗/技能/国服状态 | `data/nikke_character_dictionary_enhanced.json`（Nikke.gg 元数据 + GameKee Lv10 技能文本） |",
        "| 头像（SI 方图） | 素材库 `01_角色/立绘SI/si_cXXX_YY_s_*.png`，128×128 客户端官方头像 |",
        "| 半身像 | 素材库 `01_角色/头像/*_mi_uc_tex.png`，256×512（队伍编成队员卡 / 妮姬列表 / 名片） |",
        "| 立绘 | 素材库 `01_角色/立绘HD/*_uc_tex.png`，1024²/2048²（详情 → 立绘鉴赏） |",
        "| 头像兜底 | 无 SI 档：从半身像裁头顶方图（标 `从半身像裁切`）→ Wiki 128 小图标 |",
        "| 半身像兜底 | 无 mi 档：从素材库立绘HD 按「顶部窄条定位头部 + 内容高 40% + 1:2 画幅」裁切，标 `从立绘裁切` |",
        "| 立绘兜底 | 本地缓存 `nikke_gg_portrait.webp` → `official/<slug>/fullbody.png` |",
        "| 代号解析 | 四通道：`officialCode` → `iconId` → `dotggIconUrl` 内嵌 `si_cXXX_YY_s` → 素材库文件名中文名反查 |",
        "",
        "## 2. 覆盖",
        "",
        f"- 角色总数 **{c['characters']}**（国服已上线 {c['cnReleased']}，无客户端代号 {c['noCode']}）",
        "",
        "| 素材 | 拆包素材库 | 本地缓存 | 裁切派生 | Wiki小图标 | 未获取 |",
        "|---|---|---|---|---|---|",
    ]
    for key, label in (("icon", "头像 SI"), ("avatar", "半身像"), ("portrait", "立绘 HD")):
        s = c[key]
        lines.append(
            f"| {label} | {s['library']} | {s['cache']} | {s['derived']} | {s['wiki']} | {s['missing']} |"
        )

    approx = [
        (r["identity"]["cnName"], r["clientCode"], key, st.get("relPath") or st.get("relDir") or "")
        for r in records
        for key, st in r["assets"].items()
        if st.get("approximate")
    ]
    if approx:
        lines += [
            "",
            "### 变体近似（素材库没有该代号的原变体，改用同角色其他变体）",
            "",
            "| 中文名 | 代号 | 档位 | 实际使用的文件 |",
            "|---|---|---|---|",
        ]
        for cn, code, key, rel in approx:
            lines.append(f"| {cn} | {code} | {key} | `{rel}` |")

    lines += ["", "## 3. 非素材库来源（已兜底，非缺失）", ""]
    gaps = [
        (r["identity"]["cnName"], r["identity"]["englishName"], r["clientCode"], key, st["status"])
        for r in records
        for key, st in r["assets"].items()
        if st["status"] != "library"
    ]
    if gaps:
        lines.append("| 中文名 | 英文名 | 代号 | 缺项 | 现状 |")
        lines.append("|---|---|---|---|---|")
        for cn, en, code, key, st in gaps:
            lines.append(f"| {cn} | {en} | {code or '—'} | {key} | {FALLBACK_NOTE[st]} |")
    else:
        lines.append("头像与立绘全部来自拆包素材库。")
    lines += [
        "",
        "## 4. 客户端对账",
        "",
        "素材库全量代号（按基础 id 归并）与国服 locale、辞典三方比对：",
        "",
    ]
    audit = payload.get("clientAudit") or []
    if audit:
        cnt = Counter(a["category"] for a in audit)
        lines += [
            "| 分类 | 数量 | 含意 |",
            "|---|---|---|",
            f"| 已入典 | {cnt.get('已入典', 0)} | 辞典有条目、素材库有该代号 |",
            f"| 国服有记录·辞典未收 | {cnt.get('国服有记录·辞典未收', 0)} | 国服 locale 有 id，辞典漏收（应为 0） |",
            f"| 客户端独有·有名 | {cnt.get('客户端独有·有名', 0)} | 素材库文件名带中文名，国服 locale 无该 id（国际服 NPC / 未上国服） |",
            f"| 客户端独有·无名(NPC池) | {cnt.get('客户端独有·无名(NPC池)', 0)} | 文件名只有代号，多为 c9xxx 段群众/怪物立绘 |",
            f"| **合计** | **{len(audit)}** | 客户端素材库出现过的全部基础代号 |",
            "",
            "> 判据只认两条硬证据：国服 locale 的 `客户端 id`、素材库是否真有该代号文件。"
            "不做「看着像可玩角色就收」的推断。",
        ]
        named = [a for a in audit if a["category"] == "客户端独有·有名"]
        if named:
            lines += ["", "### 客户端独有·有名（未进国服 locale，本轮未收录）", "",
                      "| 代号 | 素材库中文名 | SI | 半身 | 立绘HD | 变体 |", "|---|---|---|---|---|---|"]
            for a in named:
                lines.append(
                    f"| {a['code']} | {a['libraryName']} | {'有' if a['icon'] else '—'} "
                    f"| {'有' if a['avatar'] else '—'} | {'有' if a['portrait'] else '—'} | {a['variants']} |"
                )

    lines += [
        "",
        "## 5. 已知缺口",
        "",
        f"- 无客户端代号记录：{c['noCode']} 条 —— "
        + (
            "、".join(f"`{r['identity']['cnName']}`" for r in records if not r["clientCode"])
            or "无"
        )
        + "。代号解析走四通道（officialCode / iconId / dotgg 图标 URL / 素材库中文名），"
        "仍未命中的只有既无 dotgg 图标、素材库又无同名文件者，其图走本地 GameKee 缓存兜底。",
        "- 这 3 条（方舟黑色游侠、灰姑娘：琉璃波光、玛律恰那：海洋进修）经确认是国服卡池内的独立可操作角色，"
        "不按 NPC 或本体皮肤处理。",
        "- SD立绘（战斗小人逐帧拆图）已明确不收，`01_角色/SD立绘/` 不再参与构建。",
        "- **素材库中文名不可全信**：`c930_00` 文件名标 `E.H.`，画面实为一只白色动物；"
        "`c515_00` 标 `灰姑娘`，与 `c511_00`（Cinderella）造型完全不同；"
        "`c510_00`/`c514_00` 同名「格拉维」为两个不同造型。以上均未擅自改名，仅在对账表中留痕，待人工核定。",
        "- 半身像档有 29 条走国际服 `_intl` 变体，画布为紧裁切（256×429~510），非国服 256×512 固定规格，"
        "混排时人物占比不一致；已在 JSON 里如实记录 `width/height`，未做拉伸或补边。",
        "- GameKee 评测攻略快照仍是 0 条（`sources/gamekee/reviews.json` 状态 `pending_route_discovery`），"
        "所以本轮「Wiki 采文本」只覆盖技能、普攻与数值，不含评价正文。",
        "",
        "## 6. 产物",
        "",
        f"- `正式产物/角色辞典.json`：结构化辞典，{c['characters']} 条，含三档素材（头像 SI / 半身像 / 立绘 HD）绝对与相对路径及兜底地址；`clientAudit` 为客户端对账明细",
        "- `正式产物/角色辞典.xlsx`：7 张表（角色总表 / 技能明细 / 普攻明细 / 素材清单 / 兜底来源 / 客户端对账 / 说明）；"
        "角色总表头像为客户端 SI 官方方图 80×80（等比缩放不裁切），列宽 12、行高 60",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="重构角色辞典")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--no-images", action="store_true", help="不在 xlsx 里嵌头像缩略图")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("需要 --dry-run 或 --apply")

    print(f"素材库: {LIBRARY_ROOT}（存在={LIBRARY_ROOT.is_dir()}）")
    lib = index_library()
    print(f"  · 索引到 {len(lib)} 个代号")

    raw = load_dictionary()
    by_base = base_index(lib)
    name_idx = library_name_index()
    print(f"  · 素材库中文名索引 {len(name_idx)} 条")
    records = []
    for rec in raw:
        assets, _ = resolve_assets(rec, lib, by_base, name_idx)
        code, code_source = resolve_code(rec, name_idx)
        records.append(build_record(rec, assets, code, code_source))
    records.sort(key=lambda r: (r["availability"]["cnReleased"] != "已上线", r["slug"]))

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "libraryRoot": LIBRARY_ROOT.as_posix(),
        "imagePolicy": "对齐客户端三档：头像=立绘SI(128²官方方图)、半身像=头像/*_mi_uc_tex(256×512)、立绘=立绘HD(1024²/2048²)；缺档才从相邻档裁切，再缺回落 Wiki 缓存并标 missing 附远程地址；SD立绘不收",
        "textPolicy": "身份/战斗取 Nikke.gg；技能与普攻取 GameKee 加点页 Lv10 快照",
        "counts": summarize(records),
        "clientAudit": audit_roster(records, lib),
        "characters": records,
    }

    c = payload["counts"]
    print(f"角色 {c['characters']}  已上线 {c['cnReleased']}  无代号 {c['noCode']}")
    for key, label in (("icon", "头像SI"), ("avatar", "半身像"), ("portrait", "立绘HD")):
        s = c[key]
        print(
            f"  {label:7s} 素材库 {s['library']:3d} / 缓存 {s['cache']:3d} / 裁切 {s['derived']:3d}"
            f" / 小图标 {s['wiki']:3d} / 未获取 {s['missing']:3d}"
        )

    if args.dry_run:
        print("\n[dry-run] 未写入任何文件")
        return 0

    write_json(payload)
    print(f"已写入 {OUT_JSON}")
    write_xlsx(payload, with_images=not args.no_images)
    print(f"已写入 {OUT_XLSX}（{OUT_XLSX.stat().st_size/1048576:.1f} MB）")
    report = write_report(payload, records)
    print(f"已写入报告 {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
