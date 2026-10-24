"""把「国服客户端本地化库」取证结果写入增强词典与国服状态表。

输入：data/character_repository/sources/cn_client_20261021/cn_locale_character.json
      （由 scripts/extract_cn_locale_from_device.py 生成，含 tier / dictionaryEntry）
输出：data/nikke_character_dictionary_enhanced.json
      data/cn_release_status.json
      data/reports/cn_client_roster_apply_report.json
      data/character_repository/sources/cn_client_20261021/pending_missing_playable.csv

判定规则（按用户裁决 A：只算「已开放获取」，预埋单列一档）：
  可操作（cv_zh_cn + stay/speech）  → 已上线
  仅名字（客户端预埋，无可玩证据）  → 预埋未开放
  待定 / 文本无语音                → 保持 待确认，只补证据
  用户确认/用户更正过的条目        → 永不改写状态（用户优先级最高）
  已是「已上线」的条目              → 永不降级，只补证据

用法：
  python scripts/apply_cn_client_roster.py --dry-run
  python scripts/apply_cn_client_roster.py --apply
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICT = DATA / "nikke_character_dictionary_enhanced.json"
STATUS = DATA / "cn_release_status.json"
CLIENT = DATA / "character_repository" / "sources" / "cn_client_20261021" / "cn_locale_character.json"
ARCHIVE = DATA / "archive"
REPORTS = DATA / "reports"
TZ = timezone(timedelta(hours=8))

USER_BASIS_PREFIXES = ("用户确认", "用户更正", "用户提供")
# 词典侧没有 iconId、只能按客户端 id 人工对齐的条目（已核对英文名唯一）
MANUAL_ID_MAP = {870: "Queen (Makoto)", 871: "Yukiko", 872: "Aigis"}
# 按名对齐后的译名订正
# Volume：国服客户端 Locale_Character.lss 写的是「沃纶姆」，玩家社区/GameKee 用「沃伦姆」。
# 2026-10-23 用户裁决——统一显示「沃伦姆」，「沃纶姆」降为别名（nikke_character_aliases.json 已收）。
# 放在这里而不是手改词典，是为了下次重跑本脚本不会被 Locale 覆盖回去。
MANUAL_NAME_FIXES = {"Aigis": "埃癸斯", "Volume": "沃伦姆"}


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def load() -> tuple[list[dict], dict, dict]:
    rows = json.loads(DICT.read_text(encoding="utf-8"))
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    client = json.loads(CLIENT.read_text(encoding="utf-8"))
    return rows, status, client


def backup() -> Path:
    stamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    dst = ARCHIVE / f"cn_client_sync_{stamp}"
    dst.mkdir(parents=True, exist_ok=True)
    for f in (DICT, STATUS):
        shutil.copy2(f, dst / f.name)
    return dst


def build_status(rows: list[dict], old: dict) -> dict:
    keep = {k: v for k, v in old.items() if k.startswith("_")}
    schema = keep.get("_schema") or {}
    schema["status_values"] = ["已上线", "未上线", "预埋未开放", "待确认"]
    schema.setdefault("fields", ["status", "date", "basis", "note"])
    schema["description"] = (
        "国服上线状态独立维护。已上线只认「可溯源国服证据」："
        "用户确认 / 国服客户端实装取证（cv_zh_cn + 看板语音）/ 公告与卡池公示。"
        "客户端仅有名称的条目记「预埋未开放」，不要用海外 Wiki 资料推断。"
    )
    out = {"_schema": schema}
    for r in rows:
        name = r.get("name")
        if not name:
            continue
        ev = r.get("cnClientEvidence") or {}
        note_parts = []
        if r.get("cnNamePrevious"):
            note_parts.append(f"中文名订正：{r['cnNamePrevious']} → {r.get('cnName')}（国服客户端）")
        if ev:
            note_parts.append(
                f"客户端 id={ev.get('charId')} 分档={ev.get('tier')} "
                f"国配={'有' if ev.get('hasCvZhCn') else '无'} 看板语音={'有' if ev.get('hasStay') else '无'}"
            )
        prev = old.get(name) or {}
        if str(prev.get("basis", "")).startswith(USER_BASIS_PREFIXES):
            note_parts.insert(0, prev.get("note", ""))
            note = "；".join(p for p in note_parts if p)
            out[name] = {
                "status": prev.get("status", "待确认"),
                "date": prev.get("date", ""),
                "basis": prev.get("basis", ""),
                "note": note,
            }
            continue
        out[name] = {
            "status": r.get("cnReleased") or "待确认",
            "date": r.get("cnReleaseDate") or prev.get("date", ""),
            "basis": r.get("releaseBasis") or "",
            "note": "；".join(p for p in note_parts if p),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        ap.error("需要 --apply 或 --dry-run")

    rows, status, client = load()
    by_name = {r.get("name"): r for r in rows if r.get("name")}
    name_to_client = {c["chineseName"]: c for c in client["characters"]}
    captured = client.get("generatedAt", "")
    device = (client.get("device") or {}).get("serial", "")

    changes = {"upgraded": [], "preloaded": [], "renamed": [], "kept_user": [], "kept_released": [], "pending": []}

    # 补齐词典缺 iconId 的少量条目（按 id 人工对齐）
    for c in client["characters"]:
        if not c.get("dictionaryEntry") and c["charId"] in MANUAL_ID_MAP:
            c["dictionaryEntry"] = MANUAL_ID_MAP[c["charId"]]
            c["nameMatchesDictionary"] = None

    for c in client["characters"]:
        entry_name = c.get("dictionaryEntry")
        row = by_name.get(entry_name) if entry_name else None
        if row is None:
            continue

        tier = c.get("tier")
        sig = c.get("signature") or {}
        evidence = {
            "charId": c["charId"],
            "clientName": c["chineseName"],
            "tier": tier,
            "hasCvZhCn": sig.get("hasCvZhCn"),
            "hasIntro": sig.get("hasIntro"),
            "hasStay": sig.get("hasStay"),
            "hasSpeech": sig.get("hasSpeech"),
            "keyCount": sig.get("keyCount"),
            "capturedAt": captured,
            "device": device,
            "sourceFile": "Locale_Character.lss",
        }
        row["cnClientEvidence"] = evidence

        cur_status = row.get("cnReleased") or "待确认"
        cur_basis = str(row.get("releaseBasis") or "")

        # 1) 中文名订正（裁决 B：中文名取国服官方名）
        if c.get("nameMatchesDictionary") is False:
            old_cn = row.get("cnName") or ""
            new_cn = c["chineseName"]
            if new_cn and new_cn != old_cn:
                row.setdefault("cnNamePrevious", old_cn)
                row["cnName"] = new_cn
                row["cnNameSource"] = "国服客户端 Locale_Character.lss"
                row["cnNameUpdatedAt"] = today()
                changes["renamed"].append({"entry": row["name"], "charId": c["charId"], "from": old_cn, "to": new_cn})

        # 2) 状态判定
        if cur_basis.startswith(USER_BASIS_PREFIXES):
            changes["kept_user"].append(row["name"])
            continue
        if cur_status == "已上线":
            changes["kept_released"].append(row["name"])
            continue
        if tier == "可操作":
            row["cnReleased"] = "已上线"
            row["releaseBasis"] = (
                f"国服客户端实装取证：Locale_Character.lss id={c['charId']}，"
                f"含 cv_zh_cn + {'看板语音' if sig.get('hasStay') else '语音台词'}（设备 {device}，{captured[:10]}）"
            )
            row["cnReleaseDate"] = row.get("cnReleaseDate") or ""
            changes["upgraded"].append({"entry": row["name"], "cnName": row.get("cnName"), "charId": c["charId"]})
        elif tier == "预埋":
            row["cnReleased"] = "预埋未开放"
            row["releaseBasis"] = (
                f"国服客户端仅有名称、无配音与看板/好感台词（id={c['charId']}，设备 {device}，{captured[:10]}）"
            )
            changes["preloaded"].append({"entry": row["name"], "cnName": row.get("cnName"), "charId": c["charId"]})
        else:
            changes["pending"].append(
                {"entry": row["name"], "cnName": row.get("cnName"), "tier": tier, "charId": c["charId"]}
            )

    # 3) 无 iconId 条目的译名订正（状态由上一步按 id 判定）
    for en, fixed in MANUAL_NAME_FIXES.items():
        row = by_name.get(en)
        if row and (row.get("cnName") or "") != fixed:
            old_cn = row.get("cnName") or ""
            row.setdefault("cnNamePrevious", old_cn)
            row["cnName"] = fixed
            row["cnNameSource"] = "国服客户端 Locale_Character.lss（按 id 对齐）"
            row["cnNameUpdatedAt"] = today()
            changes["renamed"].append({"entry": en, "charId": None, "from": old_cn, "to": fixed})

    new_status = build_status(rows, status)

    # 4) 缺册可操作名单
    missing = [
        c for c in client["characters"]
        if c.get("tier") == "可操作" and not c.get("dictionaryEntry")
    ]
    missing_path = CLIENT.parent / "pending_missing_playable.csv"
    with missing_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["角色ID", "国服中文名", "别名", "有国配", "有看板语音", "说明"])
        for c in sorted(missing, key=lambda x: x["charId"]):
            in_dict_by_name = c["chineseName"] in {r.get("cnName") for r in rows}
            w.writerow([
                c["charId"], c["chineseName"], "|".join(c.get("aliases") or []),
                "是" if c["signature"]["hasCvZhCn"] else "",
                "是" if c["signature"]["hasStay"] else "",
                "词典已有同名列（缺 iconId，需补 id）" if in_dict_by_name else "词典完全缺册，待补属性/技能数据",
            ])

    summary = {
        "generatedAt": datetime.now(TZ).isoformat(timespec="seconds"),
        "source": str(CLIENT.relative_to(ROOT)),
        "clientCapturedAt": captured,
        "device": device,
        "counts": {
            "upgraded": len(changes["upgraded"]),
            "preloaded": len(changes["preloaded"]),
            "renamed": len(changes["renamed"]),
            "keptUserConfirmed": len(changes["kept_user"]),
            "keptAlreadyReleased": len(changes["kept_released"]),
            "stillPending": len(changes["pending"]),
            "missingPlayable": len(missing),
        },
        "detail": changes,
        "missingPlayable": [
            {"charId": c["charId"], "cnName": c["chineseName"]} for c in sorted(missing, key=lambda x: x["charId"])
        ],
    }

    print(json.dumps(summary["counts"], ensure_ascii=False, indent=2))

    if args.dry_run:
        for k in ("upgraded", "preloaded", "renamed"):
            print(f"-- {k} --")
            for x in changes[k]:
                print("  ", x)
        print("(dry-run，未写文件)")
        return

    arch = backup()
    DICT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    STATUS.write_text(json.dumps(new_status, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "cn_client_roster_apply_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("备份:", arch)
    print("已写入:", DICT.name, STATUS.name, missing_path.name)


if __name__ == "__main__":
    main()
