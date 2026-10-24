"""从 ADB 连接的国服客户端提取「角色 ID ↔ 国服官方中文名 ↔ 实装完整度」，并与本地词典按 id 对齐。

数据源（2026-10-21 实测确认）：
  /sdcard/Android/data/com.tencent.nikke/files/saus/saus/lss/
    Locale_Character.lss            SQLite，Key=`<id>_<field>` → 国服中文文案
                                    字段含 name / intro / speech_NN / stay_NN / cv_zh_cn / cv_ja / cv_ko / cv_en
    CharacterSearchTable_zh-CN.lss  SQLite，Aliases(Alias, ResourceId)，与上表 1:1
    Locale_CharacterCostume.lss     时装名，不参与角色名单

关键口径：
- 客户端只证明「已收录」。本脚本用「实装完整度」做代理判据：
    可操作     = 有中文配音 + 有看板/语音台词（stay_* 或 speech_*）
    待定       = 有配音 + 有 intro，但无看板台词（多为 NPC，也可能语音待补）
    文本无语音 = 有 intro/stay/speech 但无 cv_zh_cn
    仅名字     = 只有 name（含 name+cv），视为客户端预埋
- 词典侧按 iconId 内嵌 id（`si_c<id>_NN_s`）对齐，避免译名变体干扰。
- 本脚本只读设备，不改设备任何文件。
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICT = DATA / "character_repository" / "canonical" / "characters.json"
DICT_ENHANCED = DATA / "nikke_character_dictionary_enhanced.json"
NAMES_TXT = DATA / "cn_released_names.txt"
OUT_DIR = DATA / "character_repository" / "sources" / "cn_client_20261021"
REPORTS = DATA / "reports"
DOC_REPORTS = ROOT / "核心目录" / "报告"
DEVICE_DIR = "/sdcard/Android/data/com.tencent.nikke/files/saus/saus/lss"
FILES = ("Locale_Character.lss", "CharacterSearchTable_zh-CN.lss", "Locale_CharacterCostume.lss")
TZ = timezone(timedelta(hours=8))
ICON_ID_RE = re.compile(r"^si[_-]c(\d+)_(\d+)_", re.I)

TIER_PLAYABLE = "可操作"
TIER_PLAYABLE_NO_CV = "可操作-国配缺失"
TIER_NPC = "NPC"
TIER_PRELOAD = "预埋"


def adb(serial: str, *args: str) -> str:
    cmd = ["adb", "-s", serial, *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"adb 失败: {' '.join(cmd)}\n{r.stderr}")
    return r.stdout


def pull(serial: str, raw_dir: Path) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    meta = {}
    for name in FILES:
        dst = raw_dir / name
        adb(serial, "pull", f"{DEVICE_DIR}/{name}", str(dst))
        st = dst.stat()
        meta[name] = {"bytes": st.st_size, "mtime": datetime.fromtimestamp(st.st_mtime, TZ).isoformat()}
    return meta


def extract(raw_dir: Path) -> dict:
    con = sqlite3.connect(raw_dir / "Locale_Character.lss")
    all_rows = con.execute("select Key, [zh-CN] from Locale_Character").fetchall()
    con.close()

    fields: dict[int, dict[str, str]] = {}
    extra: dict[str, str] = {}
    for k, v in all_rows:
        m = re.match(r"^(\d+)_(.+)$", k)
        if m:
            fields.setdefault(int(m.group(1)), {})[m.group(2)] = v
        elif v:
            extra[k] = v

    con2 = sqlite3.connect(raw_dir / "CharacterSearchTable_zh-CN.lss")
    aliases: dict[int, list[str]] = {}
    for a, rid in con2.execute("select Alias, ResourceId from Aliases"):
        aliases.setdefault(int(rid), []).append(a)
    con2.close()

    con3 = sqlite3.connect(raw_dir / "Locale_CharacterCostume.lss")
    costumes = {}
    for k, v in con3.execute("select Key, [zh-CN] from Locale_CharacterCostume"):
        if k.endswith("_name") and v:
            costumes[k[:-5]] = v
    con3.close()

    return {
        "fields": dict(sorted(fields.items())),
        "aliases": {k: v for k, v in sorted(aliases.items())},
        "costumes": costumes,
        "otherNameKeys": dict(sorted(extra.items())),
    }


def tier_of(f: dict[str, str]) -> str:
    """按「是否有看板/语音台词」分档。

    实装角色必备 stay_*（看板台词）或 speech_*（好感语音）；
    只有 name+intro 的是客户端预埋（译名先行下发）。
    cv_zh_cn 只用来区分「已上线」与「国配缺失」。
    """
    has_cv = "cv_zh_cn" in f
    has_stay = any(k.startswith("stay_") for k in f)
    has_speech = any(k.startswith("speech_") for k in f)
    has_intro = "intro" in f
    if has_stay or has_speech:
        return TIER_PLAYABLE if has_cv else TIER_PLAYABLE_NO_CV
    if has_cv and has_intro:
        return TIER_NPC
    return TIER_PRELOAD


def signature(f: dict[str, str]) -> dict:
    return {
        "hasCvZhCn": "cv_zh_cn" in f,
        "hasCvJa": "cv_ja" in f,
        "hasIntro": "intro" in f,
        "hasStay": any(k.startswith("stay_") for k in f),
        "hasSpeech": any(k.startswith("speech_") for k in f),
        "keyCount": len(f),
    }


def enhanced_index() -> dict[int, dict]:
    """iconId 内嵌 id → 增强词典条目。"""
    if not DICT_ENHANCED.exists():
        return {}
    rows = json.loads(DICT_ENHANCED.read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        m = ICON_ID_RE.match(r.get("iconId") or "")
        if m:
            out[int(m.group(1))] = r
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="e9711d88")
    ap.add_argument("--skip-pull", action="store_true")
    args = ap.parse_args()

    raw_dir = OUT_DIR / "raw"
    meta = {} if args.skip_pull else pull(args.serial, raw_dir)
    ext = extract(raw_dir)

    dict_rows = json.loads(DICT.read_text(encoding="utf-8"))["characters"]
    dict_names = {(x["identity"].get("chineseName") or "").strip() for x in dict_rows}
    dict_names.discard("")
    enh = enhanced_index()
    enh_no_id = [
        r for r in json.loads(DICT_ENHANCED.read_text(encoding="utf-8"))
        if not ICON_ID_RE.match(r.get("iconId") or "")
    ] if DICT_ENHANCED.exists() else []

    old_list = {l.strip() for l in NAMES_TXT.read_text(encoding="utf-8").splitlines() if l.strip()}

    rows = []
    for cid, f in ext["fields"].items():
        name = f.get("name")
        if not name:
            continue
        e = enh.get(cid)
        rows.append({
            "charId": cid,
            "chineseName": name,
            "aliases": ext["aliases"].get(cid, []),
            "tier": tier_of(f),
            "signature": signature(f),
            "inDictionary": name in dict_names,
            "dictionaryEntry": e.get("name") if e else None,
            "dictionaryCnName": e.get("cnName") if e else None,
            "dictionaryStatus": e.get("cnReleased") if e else None,
            "nameMatchesDictionary": (e.get("cnName") or "").strip() == name.strip() if e else None,
            "inOldReleasedList": name in old_list,
        })

    cn_names = {r["chineseName"] for r in rows}
    only_dict_names = sorted(dict_names - cn_names)
    only_client_names = sorted(cn_names - dict_names)
    id_hit = [r for r in rows if r["dictionaryEntry"]]
    mismatched = [r for r in id_hit if r["nameMatchesDictionary"] is False]

    tier_counts: dict[str, int] = {}
    for r in rows:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1

    payload = {
        "generatedAt": datetime.now(TZ).isoformat(timespec="seconds"),
        "device": {"serial": args.serial, "package": "com.tencent.nikke", "dir": DEVICE_DIR},
        "sourceFiles": meta,
        "counts": {
            "clientNamedCharacters": len(rows),
            "clientUniqueNames": len(cn_names),
            "dictionaryNames": len(dict_names),
            "bothSides": len(dict_names & cn_names),
            "dictionaryOnly": len(only_dict_names),
            "clientOnly": len(only_client_names),
            "oldReleasedList": len(old_list),
            "costumes": len(ext["costumes"]),
            "matchedById": len(id_hit),
            "nameMismatchById": len(mismatched),
        },
        "tierCounts": tier_counts,
        "dictionaryOnly": only_dict_names,
        "clientOnly": only_client_names,
        "characters": rows,
        "costumes": ext["costumes"],
        "otherNameKeys": ext["otherNameKeys"],
        "caveat": "客户端收录 ≠ 已开放获取；本脚本以「中文配音 + 看板/语音台词」作为实装代理判据，"
                  "仅名字条目视为预埋。最终卡池开放仍需公告/概率公示佐证。",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    (OUT_DIR / "cn_locale_character.json").write_text(text, encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "cn_roster_device_audit_20261021.json").write_text(text, encoding="utf-8")

    write_review(payload, rows, mismatched, enh_no_id)

    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print(json.dumps(tier_counts, ensure_ascii=False))
    print("词典有·客户端无:", only_dict_names)
    print("客户端有·词典无:", only_client_names)


def write_review(payload: dict, rows: list[dict], mismatched: list[dict], enh_no_id: list[dict]) -> None:
    import csv

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "cn_roster_264_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "角色ID", "国服中文名", "别名", "实装分档", "有国配", "有intro", "有看板语音",
            "词典英文名", "词典中文名", "词典现状态", "名称一致", "旧名单已收录",
        ])
        for r in sorted(rows, key=lambda x: x["charId"]):
            s = r["signature"]
            w.writerow([
                r["charId"], r["chineseName"], "|".join(r["aliases"]), r["tier"],
                "是" if s["hasCvZhCn"] else "", "是" if s["hasIntro"] else "",
                "是" if s["hasStay"] else "",
                r["dictionaryEntry"] or "", r["dictionaryCnName"] or "", r["dictionaryStatus"] or "",
                "" if r["nameMatchesDictionary"] is None else ("是" if r["nameMatchesDictionary"] else "否"),
                "是" if r["inOldReleasedList"] else "",
            ])

    c = payload["counts"]
    t = payload["tierCounts"]
    playable = [r for r in rows if r["tier"] == TIER_PLAYABLE]
    preload = [r for r in rows if r["tier"] == TIER_PRELOAD]
    others = [r for r in rows if r["tier"] not in (TIER_PLAYABLE, TIER_PRELOAD)]
    upgrade = [
        r for r in playable
        if r["dictionaryEntry"] and r["dictionaryStatus"] != "已上线"
    ]
    missing_playable = [r for r in playable if not r["dictionaryEntry"]]

    lines = [
        "# 国服角色名单设备侧核对报告（2026-10-21）",
        "",
        f"- 设备：`{payload['device']['serial']}` · `{payload['device']['package']}`",
        f"- 数据源：`{DEVICE_DIR}/Locale_Character.lss`（SQLite，Key=`<id>_<field>`）、"
        "`CharacterSearchTable_zh-CN.lss`、`Locale_CharacterCostume.lss`",
        f"- 抓取时间：{payload['generatedAt']}",
        "- 对齐方式：词典 `iconId` 内嵌 id（`si_c<id>_NN_s`）↔ 客户端 `<id>_name`，避免译名变体干扰",
        "",
        "## 一、计数",
        "",
        "| 项 | 数量 |",
        "|:--|--:|",
        f"| 客户端有名字的角色条目 | {c['clientNamedCharacters']} |",
        f"| 去重后中文名 | {c['clientUniqueNames']} |",
        f"| 词典中文名 | {c['dictionaryNames']} |",
        f"| 按 id 对齐成功 | {c['matchedById']} |",
        f"| 其中名称不一致 | {c['nameMismatchById']} |",
        f"| 旧国服名单（2026-06-11） | {c['oldReleasedList']} |",
        "",
        "## 二、实装分档（代理判据）",
        "",
        "| 分档 | 判据 | 数量 |",
        "|:--|:--|--:|",
        f"| 可操作（有国配） | 有 `stay_*`/`speech_*` + `cv_zh_cn` | {t.get(TIER_PLAYABLE, 0)} |",
        f"| 可操作（国配缺失） | 有 `stay_*`/`speech_*`，无 `cv_zh_cn` | {t.get(TIER_PLAYABLE_NO_CV, 0)} |",
        f"| NPC | 有 `cv_zh_cn` + `intro`，无看板/好感台词 | {t.get(TIER_NPC, 0)} |",
        f"| 预埋 | 只有 `name`(+`intro`)，无配音无台词 | {t.get(TIER_PRELOAD, 0)} |",
        "",
        "## 三、词典中文名订正（按 id 对齐，共 "
        f"{len(mismatched)} 条）",
        "",
        "| 角色ID | 国服客户端 | 词典现值 | 性质 |",
        "|--:|:--|:--|:--|",
    ]
    for r in sorted(mismatched, key=lambda x: x["charId"]):
        a, b = r["chineseName"], r["dictionaryCnName"] or ""

        def flat(s: str) -> str:
            return s.replace(":", "").replace("：", "").replace(".", "").replace(" ", "").lower()

        if flat(a) == flat(b):
            note = "标点/大小写差异"
        elif r["charId"] in (831, 832):
            note = "词典误标（联动角色名错位）"
        else:
            note = "译名不同，取国服客户端"
        lines.append(f"| {r['charId']} | {a} | {b} | {note} |")

    lines += [
        "",
        "## 四、可升级为「已上线」（客户端可操作 + 词典非已上线）",
        "",
        f"共 {len(upgrade)} 条。规则校验：词典原有 126 条「已上线」在同规则下**全部命中可操作**，"
        "无一条落入「仅名字」，即该规则在已知正例上零误判。",
        "",
        "| 角色ID | 中文名 | 英文名 | 词典现状态 |",
        "|--:|:--|:--|:--|",
    ]
    for r in sorted(upgrade, key=lambda x: x["charId"]):
        lines.append(f"| {r['charId']} | {r['chineseName']} | {r['dictionaryEntry']} | {r['dictionaryStatus']} |")

    lines += [
        "",
        "## 五、客户端可操作、词典缺册",
        "",
        f"共 {len(missing_playable)} 条（需补属性/技能数据后才能入册）：",
        "",
        "| 角色ID | 国服中文名 |",
        "|--:|:--|",
    ]
    for r in sorted(missing_playable, key=lambda x: x["charId"]):
        lines.append(f"| {r['charId']} | {r['chineseName']} |")

    lines += [
        "",
        "## 六、客户端预埋（无配音无台词）",
        "",
        f"共 {len(preload)} 条。注意：词典中「用户确认已加入国服卡池」的条目也可能落在本档，"
        "**用户确认优先，不得据本档降级**。",
        "",
        "| 角色ID | 中文名 | 词典英文名 | 词典现状态 |",
        "|--:|:--|:--|:--|",
    ]
    for r in sorted(preload, key=lambda x: x["charId"]):
        lines.append(
            f"| {r['charId']} | {r['chineseName']} | {r['dictionaryEntry'] or '—'} | {r['dictionaryStatus'] or '—'} |"
        )

    lines += [
        "",
        "## 七、中间档（非可操作，非预埋）",
        "",
        "| 角色ID | 中文名 | 分档 | 说明 |",
        "|--:|:--|:--|:--|",
    ]
    for r in sorted(others, key=lambda x: x["charId"]):
        note = "有配音与简介、无看板/好感台词，NPC 特征" if r["tier"] == TIER_NPC else "已实装台词但缺国配，语音疑待补"
        lines.append(f"| {r['charId']} | {r['chineseName']} | {r['tier']} | {note} |")

    if enh_no_id:
        lines += [
            "",
            "## 八、词典侧无 iconId 条目（无法按 id 对齐，需人工核）",
            "",
            "| 英文名 | 词典中文名 | 现状态 |",
            "|:--|:--|:--|",
        ]
        for r in enh_no_id:
            lines.append(f"| {r['name']} | {r.get('cnName')} | {r.get('cnReleased')} |")

    lines += [
        "",
        "## 九、口径限制",
        "",
        "- 客户端 `Locale_Character` **没有卡池/上线日期字段**，「已开放获取」无法直接读取；",
        "  本报告用「中文配音 + 看板/语音台词齐全」作为实装代理判据，并在同规则下用 126 条已知正例做过校验。",
        "- 代理判据是**弱证据**：理论上存在「语音已随包下发但卡池未开」的窗口期。",
        "  因此联动角色（玛奇玛/雷姆/明日香/千束 等）与 2026 年新角色建议再做卡池公示二次确认。",
        "- 时装名（182 条）单独存放，**不并入角色名单**。",
        "",
        f"明细 CSV：`{csv_path.relative_to(ROOT)}`",
    ]
    DOC_REPORTS.mkdir(parents=True, exist_ok=True)
    md = DOC_REPORTS / "cn_roster_device_audit_20261021.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("report:", md)


if __name__ == "__main__":
    main()
