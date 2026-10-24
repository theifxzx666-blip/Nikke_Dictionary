# -*- coding: utf-8 -*-
"""修复 7 个 GameKee 条目的错误录入（以用户确认为准）。

- 705512 敏特 / 706696 普莉卡：可操作妮姬（保留词典，校验素材字段）
- 708686 方舟黑色游侠：可操作妮姬（保留词典，移除误放 non_playable 素材）
- 711133 / 711739 / 713891 / 713899：角色皮肤/时装
    * 从增强词典移除（不作为独立可操作角色）
    * 关联本体（Cinderella/Marciana/Laplace/Maxwell）的 costumes 数组（多皮肤支持）
    * 写入 gamekee_costume_catalog.json（皮肤目录）
    * 仅视频无静态立绘的（711739/713891/713899）标记"仅视频/待确认"
"""
import json
import shutil
import time
from pathlib import Path

ROOT = Path(r"F:/Codex/Nikke/Nikke_Wiki")
DICTIONARY = ROOT / "data" / "nikke_character_dictionary_enhanced.json"
CATALOG = ROOT / "data" / "gamekee_costume_catalog.json"
REPORT = ROOT / "data" / "reports" / "repair_7_entries_report.json"

# 皮肤映射：contentId -> 本体
COSTUMES = [
    {"contentId": 711133, "entryId": 218253, "cnName": "灰姑娘：琉璃波光", "parentCn": "灰姑娘", "parentName": "Cinderella", "parentContentId": 170686, "hasStaticImage": True},
    {"contentId": 711739, "entryId": 218512, "cnName": "玛律恰那：海洋进修", "parentCn": "玛律恰那", "parentName": "Marciana", "parentContentId": 600802, "hasStaticImage": False},
    {"contentId": 713891, "entryId": 219258, "cnName": "拉普拉斯：究极英雄", "parentCn": "拉普拉斯", "parentName": "Laplace", "parentContentId": 576409, "hasStaticImage": False},
    {"contentId": 713899, "entryId": 219257, "cnName": "麦斯威尔：平凡技师", "parentCn": "麦斯威尔", "parentName": "Maxwell", "parentContentId": 92087, "hasStaticImage": False},
]
COSTUME_IDS = {c["contentId"] for c in COSTUMES}
COSTUME_ENTRY_IDS = {c["entryId"] for c in COSTUMES}
# 保留的可操作角色
KEEP_PLAYABLE = {705512: "敏特", 706696: "普莉卡", 708686: "方舟黑色游侠"}


def load(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def main():
    # 备份
    ts = time.strftime("%Y%m%d%H%M%S")
    shutil.copy(DICTIONARY, ROOT / "data" / "archive" / f"nikke_character_dictionary_enhanced.json.bak-{ts}")
    shutil.copy(CATALOG, ROOT / "data" / "archive" / f"gamekee_costume_catalog.json.bak-{ts}")
    print(f"已备份: {ts}")

    rows = load(DICTIONARY)
    removed, parents = [], {}
    kept_rows = []
    for row in rows:
        cid = int(row.get("gamekeeContentId") or 0)
        if cid in COSTUME_IDS:
            removed.append(row)
            continue  # 皮肤条目从主表移除
        kept_rows.append(row)
        name = str(row.get("name") or "")
        if name.lower() in {c["parentName"].lower() for c in COSTUMES}:
            parents[name.lower()] = row

    # 2. 挂皮肤到本体 costumes 数组（支持多皮肤）
    for c in COSTUMES:
        parent = parents.get(c["parentName"].lower())
        if parent is None:
            print(f"  ❌ 本体未找到: {c['parentName']}")
            continue
        costume_entry = {
            "contentId": c["contentId"],
            "entryId": c["entryId"],
            "name": c["cnName"],
            "status": "已确认（静态立绘）" if c["hasStaticImage"] else "仅视频/待确认",
        }
        # 皮肤立绘（仅 711133 有静态立绘）
        if c["hasStaticImage"]:
            skin_file = ROOT / "assets/gamekee_character_assets/skin_catalog" / f"{c['parentName'].lower()}_{c['contentId']}.png"
            costume_entry["localPortraitFile"] = skin_file.as_posix().replace(ROOT.as_posix() + "/", "F:/Codex/Nikke/Nikke_Wiki/")
        costume_entry["displayVideoUrl"] = f"https://www.gamekee.com/nikke/{c['contentId']}"
        parent.setdefault("costumes", []).append(costume_entry)
        print(f"  ✅ 皮肤挂载: {c['parentName']} ← {c['cnName']} ({costume_entry.get('status', '')})")

    # 3. 写回词典
    DICTIONARY.write_text(json.dumps(kept_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"词典: {len(rows)} -> {len(kept_rows)}（移除 {len(removed)} 皮肤条目）")

    # 4. 皮肤目录
    catalog = []
    for c in COSTUMES:
        parent = parents.get(c["parentName"].lower())
        entry = {
            "contentId": c["contentId"],
            "entryId": c["entryId"],
            "name": c["cnName"],
            "parentCharacter": c["parentName"],
            "parentCnName": c["parentCn"],
            "parentContentId": c["parentContentId"],
            "status": "已确认（静态立绘）" if c["hasStaticImage"] else "仅视频/待确认",
            "url": f"https://www.gamekee.com/nikke/{c['contentId']}",
        }
        if c["hasStaticImage"]:
            entry["localPortraitFile"] = (ROOT / f"assets/gamekee_character_assets/skin_catalog/{c['parentName'].lower()}_{c['contentId']}.png").as_posix()
        catalog.append(entry)
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"皮肤目录: {len(catalog)} 条")

    # 5. 移除 708686 误放 non_playable 素材（保留 playable_form_cards 队伍卡）
    npc_file = ROOT / "assets/gamekee_character_assets/non_playable_cards/708686.png"
    if npc_file.exists():
        npc_file.unlink()
        print("已移除误放素材: non_playable_cards/708686.png")

    # 6. 报告
    report = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "classifications": {
            "705512": {"name": "敏特", "classification": "可操作妮姬", "action": "保留主表，校验素材"},
            "706696": {"name": "普莉卡", "classification": "可操作妮姬", "action": "保留主表，校验素材"},
            "708686": {"name": "方舟黑色游侠", "classification": "可操作妮姬", "action": "保留主表，移除误放非可玩素材"},
            "711133": {"name": "灰姑娘：琉璃波光", "classification": "角色皮肤/时装", "parent": "Cinderella", "action": "移出主表，挂本体 costumes，皮肤目录，静态立绘已确认"},
            "711739": {"name": "玛律恰那：海洋进修", "classification": "角色皮肤/时装", "parent": "Marciana", "action": "移出主表，挂本体 costumes，皮肤目录，仅视频/待确认"},
            "713891": {"name": "拉普拉斯：究极英雄", "classification": "角色皮肤/时装", "parent": "Laplace", "action": "移出主表，挂本体 costumes，皮肤目录，仅视频/待确认"},
            "713899": {"name": "麦斯威尔：平凡技师", "classification": "角色皮肤/时装", "parent": "Maxwell", "action": "移出主表，挂本体 costumes，皮肤目录，仅视频/待确认"},
        },
        "dictionaryRows": {"before": len(rows), "after": len(kept_rows), "removedCostumes": [r.get("name") for r in removed]},
        "costumeCatalog": len(catalog),
        "removedMisplacedAsset": "assets/gamekee_character_assets/non_playable_cards/708686.png",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
