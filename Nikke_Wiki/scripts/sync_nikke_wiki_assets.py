import json
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ASSET_DIR = PROJECT_ROOT / "assets"
NIKKE_CHARS = DATA_DIR / "nikke_characters.json"
GAMEKEE_ENTRIES = DATA_DIR / "gamekee_character_entries.json"
NIKKE_ICON_DIR = ASSET_DIR / "nikke_character_icons"
GAMEKEE_ICON_DIR = ASSET_DIR / "gamekee_character_icons"
ALIASES = DATA_DIR / "nikke_character_aliases.json"
MATCH_REPORT = DATA_DIR / "reports" / "nikke_gamekee_match_report.json"


MANUAL_CN = {
    "2B": "2B",
    "A2": "A2",
    "Ada": "艾达",
    "Ade": "爱德",
    "Ade: Agent Bunny": "爱德：特务兔女郎",
    "Admi": "艾德米",
    "Alice": "爱丽丝",
    "Alice: Wonderland Bunny": "爱丽丝：仙境兔女郎",
    "Anchor": "安克",
    "Anchor: Innocent Maid": "安克：天真的女仆",
    "Anis": "阿妮斯",
    "Anis: Sparkling Summer": "阿妮斯：闪耀夏日",
    "Anis: Star": "阿妮斯：超级巨星",
    "Anne: Miracle Fairy": "安妮：奇迹仙女",
    "Arcana": "阿尔卡娜",
    "Arcana: Fortune Mate": "阿尔卡娜：命运伴侣",
    "Aria": "阿莉亚",
    "Asuka": "明日香",
    "Asuka: WILLE": "明日香：WILLE",
    "Avistar": "阿维斯塔",
    "Bay": "贝伊",
    "Biscuit": "饼干",
    "Blanc": "布兰儿",
    "Bready": "布蕾德",
    "Brid": "布丽德",
    "Brid: Silent Track": "布丽德：静默轨道",
    "Centi": "桑迪",
    "Chime": "钟鸣",
    "Chisato": "千束",
    "Cinderella": "灰姑娘",
    "Clay": "克莱伊",
    "Cocoa": "可可",
    "Crow": "克拉乌",
    "Crown": "皇冠",
    "Crust": "克劳斯特",
    "D": "D",
    "D: Killer Wife": "D：杀手妻子",
    "Delta": "德尔塔",
    "Delta: Ninja Thief": "德尔塔：怪盗忍者",
    "Diesel": "迪塞尔",
    "Diesel: Winter Sweets": "迪塞尔：冬日甜心",
    "Dolla": "朵拉",
    "Dorothy": "桃乐丝",
    "Dorothy: Serendipity": "桃乐丝：机缘巧遇",
    "Drake": "德雷克",
    "E.H.": "E.H.",
    "EVE": "伊芙",
    "Ein": "爱因",
    "Elegg": "伊莱格",
    "Elegg: Boom and Shock": "伊莱格：BOOM与惊吓",
    "Emilia": "艾米莉亚",
    "Emma": "艾玛",
    "Emma: Tactical Upgrade": "艾玛：战术升级",
    "Epinel": "艾菲涅尔",
    "Eunhwa": "银华",
    "Eunhwa: Tactical Upgrade": "银华：战术升级",
    "Exia": "艾可希雅",
    "Flora": "芙罗拉",
    "Folkwang": "富克旺",
    "Frima": "普琳玛",
    "Grave": "格拉维",
    "Guillotine": "吉萝婷",
    "Guillotine: Winter Slayer": "吉萝婷：寒冬杀手",
    "Guilty": "吉尔提",
    "Harran": "哈兰",
    "Helm": "海伦",
    "Helm: Aquamarine": "海伦：海蓝宝石",
    "Isabel": "伊莎贝尔",
    "Jackal": "豺狼",
    "Jill": "吉儿",
    "Julia": "尤莉亚",
    "K": "K",
    "Kilo": "基洛",
    "Label": "蕾贝儿",
    "Laplace": "拉普拉斯",
    "Leona": "蕾欧娜",
    "Liberalio": "莉贝雷利奥",
    "Liter": "丽塔",
    "Little Mermaid": "小美人鱼",
    "Ludmilla": "露德米拉",
    "Ludmilla: Winter Owner": "露德米拉：冬日之主",
    "Maiden": "梅登",
    "Maiden: Ice Rose": "梅登：冰玫瑰",
    "Makima": "玛奇玛",
    "Mana": "玛娜",
    "Marciana": "玛律恰那",
    "Mari": "真希波",
    "Mary": "玛丽",
    "Mary: Bay Goddess": "玛丽：海湾女神",
    "Mast": "马斯特",
    "Mast: Romantic Maid": "马斯特：浪漫的女仆",
    "Maxwell": "麦斯威尔",
    "Mica": "米卡",
    "Mica: Snow Buddy": "米卡：雪地伙伴",
    "Mihara": "米哈拉",
    "Mihara: Bonding Chain": "米哈拉：羁绊锁链",
    "Milk": "米尔克",
    "Milk: Blooming Bunny": "米尔克：花漾兔女郎",
    "Mint": "敏特",
    "Miranda": "米兰达",
    "Modernia": "神罚",
    "Moran": "牡丹",
    "Mori": "莫莉",
    "N102": "N102",
    "Naga": "娜嘉",
    "Nayuta": "娜由塔",
    "Neon": "尼恩",
    "Neon: Blue Ocean": "尼恩：蓝色海洋",
    "Neon: Vision Eye": "尼恩：透视之眼",
    "Nero": "尼罗",
    "Neve": "尼夫",
    "Nihilister": "尼希利斯塔",
    "Noah": "诺雅",
    "Noir": "诺瓦尔",
    "Noise": "诺伊斯",
    "Novel": "诺薇尔",
    "Pascal": "帕斯卡",
    "Pepper": "佩珀",
    "Phantom": "魅影",
    "Poli": "波莉",
    "Power": "帕瓦",
    "Prika": "普莉卡",
    "Privaty": "普丽瓦蒂",
    "Privaty: Unkind Maid": "普丽瓦蒂：不友善的女仆",
    "Quency": "昆西",
    "Quency: Escape Queen": "昆西：逃脱女王",
    "Quiry": "基里",
    "Rapi": "拉毗",
    "Rapi: Red Hood": "拉毗：小红帽",
    "Rapunzel": "长发公主",
    "Rapunzel: Pure Grace": "长发公主：纯洁恩典",
    "Raven": "渡鸦",
    "Red Hood": "小红帽",
    "Rei": "莱伊",
    "Rei Ayanami": "零",
    "Rei Ayanami (Tentative Name)": "零（暂称）",
    "Rem": "蕾姆",
    "Rosanna": "罗珊娜",
    "Rosanna: Chic Ocean": "罗珊娜：高雅海洋",
    "Rouge": "露姬",
    "Rumani": "露玛妮",
    "Rupee": "露菲",
    "Rupee: Winter Shopper": "露菲：冬日购物狂",
    "Sakura": "樱花",
    "Sakura Suzuhara": "铃原樱",
    "Sakura: Bloom in Summer": "樱花：夏日绽放",
    "Scarlet": "红莲",
    "Scarlet: Black Shadow": "红莲：暗影",
    "Signal": "西格娜",
    "Sin": "森",
    "Snow Crane": "白鹤",
    "Snow White": "白雪公主",
    "Snow White: Heavy Arms": "白雪公主：重型武装",
    "Snow White: Innocent Days": "白雪公主：纯真年代",
    "Soda": "苏打",
    "Soda: Twinkling Bunny": "苏打：闪亮兔女郎",
    "Soline": "索林",
    "Soline: Frost Ticket": "索林：霜之旅票",
    "Sora": "索拉",
    "Sugar": "舒格",
    "Takina": "泷奈",
    "Tia": "蒂娅",
    "Tove": "托比",
    "Trina": "特蕾娜",
    "Trony": "特罗尼",
    "Velvet": "薇尔维特",
    "Vesti": "贝斯蒂",
    "Vesti: Tactical Upgrade": "贝斯蒂：战术升级",
    "Viper": "毒蛇",
    "Volume": "沃纶姆",
    "Yan": "杨",
    "Yulha": "尤尔夏",
    "Yuni": "尤妮",
    "Zwei": "茨瓦伊",
    "Product 08": "量产型08",
    "Product 12": "量产型12",
    "Product 23": "量产型23",
    "Soldier EG": "士兵EG",
    "Soldier FA": "士兵FA",
    "Soldier OW": "士兵OW",
    "iDoll Flower": "iDoll花",
    "iDoll Ocean": "iDoll海",
    "iDoll Sun": "iDoll太阳",
}


def request(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def download_dotgg_icons(chars: list[dict]) -> None:
    NIKKE_ICON_DIR.mkdir(exist_ok=True)
    for ch in chars:
        out = NIKKE_ICON_DIR / f"{ch['url']}.webp"
        if out.exists() and out.stat().st_size > 0:
            continue
        url = f"https://static.dotgg.gg/nikke/characters/{ch['img']}.webp"
        try:
            out.write_bytes(request(url))
        except Exception as exc:
            print(f"[warn] dotgg icon failed {ch['name']}: {exc}")


def download_gamekee_icons(entries: list[dict]) -> None:
    GAMEKEE_ICON_DIR.mkdir(exist_ok=True)
    for row in entries:
        if not row.get("icon"):
            continue
        out = GAMEKEE_ICON_DIR / f"{row['gamekeeEntryId']}.png"
        if out.exists() and out.stat().st_size > 0:
            continue
        try:
            out.write_bytes(request(row["icon"]))
        except Exception as exc:
            print(f"[warn] gamekee icon failed {row['cnName']}: {exc}")


def feature(path: Path) -> np.ndarray:
    img = ImageOps.exif_transpose(Image.open(path).convert("RGB"))
    w, h = img.size
    # Keep the face-heavy upper-middle region. Works for both square icons and GameKee portraits.
    crop = img.crop((int(w * 0.18), int(h * 0.05), int(w * 0.82), int(h * 0.72)))
    small = crop.resize((48, 48), Image.Resampling.LANCZOS)
    arr = np.asarray(ImageOps.grayscale(small), dtype=np.float32) / 255.0
    arr = (arr - arr.mean()) / (arr.std() + 1e-6)
    rgb = np.asarray(crop.resize((24, 24), Image.Resampling.LANCZOS), dtype=np.float32) / 255.0
    hist = []
    for c in range(3):
        values, _ = np.histogram(rgb[:, :, c], bins=16, range=(0, 1), density=True)
        hist.extend(values.tolist())
    vec = np.concatenate([arr.reshape(-1), np.asarray(hist, dtype=np.float32)])
    return vec / (np.linalg.norm(vec) + 1e-6)


def main() -> None:
    chars = json.loads(NIKKE_CHARS.read_text(encoding="utf-8"))
    entries = json.loads(GAMEKEE_ENTRIES.read_text(encoding="utf-8"))
    download_dotgg_icons(chars)
    download_gamekee_icons(entries)

    gamekee_by_cn = {e["cnName"]: e for e in entries}
    aliases = json.loads(ALIASES.read_text(encoding="utf-8")) if ALIASES.exists() else {}

    report = []
    for ch in chars:
        cn = MANUAL_CN.get(ch["name"], "")
        g = gamekee_by_cn.get(cn)
        status = "matched_by_cn" if g else "missing_gamekee_cn"
        report.append({
            "name": ch["name"],
            "url": ch["url"],
            "cnName": cn,
            "gamekeeEntryId": g["gamekeeEntryId"] if g else None,
            "gamekeeIcon": g["icon"] if g else "",
            "dotggIconFile": str(NIKKE_ICON_DIR / f"{ch['url']}.webp"),
            "status": status,
        })
        if cn:
            old = aliases.get(ch["name"], [])
            merged = []
            for x in [cn, *old]:
                if x and x not in merged:
                    merged.append(x)
            aliases[ch["name"]] = merged

    MATCH_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ALIASES.write_text(json.dumps(dict(sorted(aliases.items())), ensure_ascii=False, indent=2), encoding="utf-8")
    missing_icons = [ch["name"] for ch in chars if not (NIKKE_ICON_DIR / f"{ch['url']}.webp").exists()]
    missing_cn = [r for r in report if not r["cnName"]]
    unmatched_cn = [r for r in report if r["cnName"] and r["status"] != "matched_by_cn"]
    print(json.dumps({
        "dotggCharacters": len(chars),
        "gamekeeEntries": len(entries),
        "dotggMissingIcons": len(missing_icons),
        "manualCnFilled": len([r for r in report if r["cnName"]]),
        "matchedByGameKeeCn": len([r for r in report if r["status"] == "matched_by_cn"]),
        "cnNotFoundInGameKee": unmatched_cn[:20],
        "missingIcons": missing_icons[:20],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
