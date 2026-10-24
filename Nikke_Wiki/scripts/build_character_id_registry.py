"""建立「客户端代号 -> 权威名称 / 实装状态」主表，并用国际服名单裁决汉化冲突。

判据分层（只认可溯源证据，不按外形推断）：
  (1) 国服 locale（`data/character_repository/sources/cn_client_20261021/`）
      中文名与「可操作 / 可操作-国配缺失 / 预埋 / NPC」分档的唯一权威。
      分档判据 = 有国配 + 有看板/好感语音 -> 可操作；只有 name -> 预埋。
  (2) 国际服名单（`data/nikke_characters.json` + `cache/prydwen/nikke_roster.json`）
      判定「国际服是否已上线为可操作角色」。prydwen 只收可操作角色。
  (3) 增强词典（`cnName` / `iconId`）—— 代号与中文名/英文名互译。
  (4) 拆包素材库（`00_资源库/01_角色`）—— 只证明资源存在，**不证明名字正确**。

异常类型：
  name_conflict   同一中文名落在多个有立绘的代号上
  name_truncated  素材库文件名用了 locale 全名的前缀（丢了「：形态名」后缀）
  name_mismatch   素材库名与 locale 名对不上（既不相等也不是前缀）
  no_cn_name      locale 无此代号（客户端有立绘但没有中文名）
  no_assets       locale 有名，素材库没有三档资源

用法：
    python scripts/build_character_id_registry.py --dry-run
    python scripts/build_character_id_registry.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "核心目录" / "报告"
LIBRARY_ROOT = Path(r"F:\Codex\Nikke\Nikke_Skills\拆包\00_资源库\01_角色")
CN_ROSTER = DATA / "character_repository" / "sources" / "cn_client_20261021" / "cn_roster_264_review.csv"
LOCALE_DB = DATA / "character_repository" / "sources" / "cn_client_20261021" / "raw" / "Locale_Character.lss"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
GG_ROSTER = DATA / "nikke_characters.json"
PRY_CACHE = ROOT / "cache" / "prydwen" / "nikke_roster.json"
OUT_JSON = DATA / "character_id_registry.json"

CODE_RE = re.compile(r"c0*(\d+)_0*(\d+)")
# 素材库文件名：`<中文名>_c<id>_<变体>_<后缀>.png` / `c<id>_<变体>_<后缀>.png` / `si_c<id>_<变体>_s_*.png`
# 两条正则必须分开：先试无名字前缀的裸代号，否则 `c917_00_*` 会让可选前缀把 `c917` 当成名字、id 解析成 0。
BARE_RE = re.compile(r"^c0*(?P<id>\d+)_(?P<var>\d+)_(?P<rest>.+)$")
NAME_RE = re.compile(r"^(?P<nm>.+?)_c0*(?P<id>\d+)_(?P<var>\d+)_(?P<rest>.+)$")
SI_RE = re.compile(r"^si_c0*(?P<id>\d+)_0*(?P<var>\d+)_")
SKIP_NAMES = {"si", "mi", "sd"}
LIBRARY_DIRS = ("头像", "立绘HD", "立绘SI", "立绘")
KINDS = {"头像": "avatar", "立绘HD": "portrait", "立绘SI": "icon", "立绘": "compact"}

# prydwen 用全名/别名，词典用短名时的人工桥接表（仅收录已核对项）
PRY_EXPLICIT = {
    "ada-wong": 840,
    "aigis": 872,
    "asuka-shikinami-langley": 835,
    "asuka-shikinami-langley-wille": 835,
    "chisato-nishikigi": 860,
    "cinderella-crystal-wave": 515,
    "claire-redfield": 842,
    "jill-valentine": 841,
    "mari-makinami-illustrious": 832,
    "misato-katsuragi": 836,
    "queen-makoto": 870,
    "takina-inoue": 861,
    "yukiko": 871,
    "ark-ranger-black": 570,
    "siren": 340,
    "prika": 601,
    "blue-ocean-neon": 14,
    "sparkling-summer-anis": 15,
    "innocent-dayss-snow-white": 471,
    "miracle-fairy-anne": 315,
    "winter-shopper-rupee": 322,
    "product-08": 302,
    "product-12": 303,
    "product-23": 307,
    "red-hood": 470,
}


def norm(text: str) -> str:
    """归一化名称：全半角标点、空白、大小写、& 连接符都不参与比较。"""
    if not text:
        return ""
    table = str.maketrans({"：": ":", "．": ".", "（": "(", "）": ")", "　": ""})
    return re.sub(r"[\s&・]", "", text.translate(table)).lower()


def load_cn_roster() -> dict[int, dict]:
    if not CN_ROSTER.is_file():
        raise SystemExit(f"缺少国服 locale 名单：{CN_ROSTER}")
    rows = list(csv.DictReader(CN_ROSTER.open(encoding="utf-8-sig")))
    return {
        int(r["角色ID"]): {
            "cnName": (r["国服中文名"] or "").strip(),
            "tier": (r["实装分档"] or "").strip(),
            "alias": (r["别名"] or "").strip(),
            "hasCv": (r["有国配"] or "").strip() == "是",
            "hasBoard": (r["有看板语音"] or "").strip() == "是",
        }
        for r in rows
        if r.get("角色ID", "").strip().isdigit()
    }


def load_locale_fields() -> dict[int, dict]:
    """统计每个角色 id 在 locale 库里填了多少字段。

    判据来源：真实角色的条目有 `name` + `intro` + `cv_zh_cn` + `stay_*`/`speech_*`；
    客户端预埋的**占位槽位只填 `name` 一个字段**，值是别的角色的名字（复用），
    这正是「E.H. 落在两个 id」「格拉维 落在两个 id」的成因。
    """
    if not LOCALE_DB.is_file():
        return {}
    import sqlite3

    conn = sqlite3.connect(f"file:{LOCALE_DB}?mode=ro", uri=True)
    try:
        rows = conn.execute('SELECT Key, [zh-CN] FROM Locale_Character').fetchall()
    finally:
        conn.close()
    stats: dict[int, dict] = {}
    for key, value in rows:
        cid, _, field = str(key).partition("_")
        if not cid.isdigit():
            continue
        entry = stats.setdefault(int(cid), {"fields": 0, "hasIntro": False, "hasCv": False,
                                            "hasVoice": False, "hasBoard": False})
        entry["fields"] += 1
        base = field.split("_")[-1] if field else ""
        if field == "intro":
            entry["hasIntro"] = True
        elif field.startswith("cv_zh_cn"):
            entry["hasCv"] = True
        elif field.startswith("speech"):
            entry["hasVoice"] = True
        elif field.startswith("stay"):
            entry["hasBoard"] = True
        elif base and field.startswith("speech"):
            entry["hasVoice"] = True
    for entry in stats.values():
        # 只有 name 一个字段 = 客户端占位槽位，名字不可信
        entry["placeholder"] = entry["fields"] <= 1 and not (
            entry["hasIntro"] or entry["hasCv"] or entry["hasVoice"] or entry["hasBoard"]
        )
    return stats


def load_dictionary() -> tuple[dict[int, dict], dict[str, int]]:
    raw = json.loads(DICTIONARY.read_text(encoding="utf-8-sig"))
    by_id: dict[int, dict] = {}
    by_name: dict[str, int] = {}
    for row in raw:
        m = CODE_RE.search(row.get("iconId") or "")
        if not m:
            continue
        cid = int(m.group(1))
        by_id[cid] = row
        for key in (row.get("name"), row.get("cnName")):
            if key:
                by_name.setdefault(norm(key), cid)
    return by_id, by_name


def load_intl() -> tuple[dict[int, set[str]], dict[str, int]]:
    """返回 (国际服可操作 id -> 英文名集合, 英文名归一 -> id)。"""
    gg = json.loads(GG_ROSTER.read_text(encoding="utf-8-sig"))
    playable: dict[int, set[str]] = defaultdict(set)
    name_index: dict[str, int] = {}
    for row in gg:
        m = CODE_RE.search(row.get("img") or "")
        if not m:
            continue
        cid = int(m.group(1))
        playable[cid].add(row["name"])
        name_index.setdefault(norm(row["name"]), cid)
    return playable, name_index


def map_prydwen(playable: dict[int, set[str]], name_index: dict[str, int]) -> tuple[list[dict], list[dict]]:
    """把 prydwen 名单映射到代号；返回 (命中项, 未命中项)。"""
    if not PRY_CACHE.is_file():
        return [], []
    roster = json.loads(PRY_CACHE.read_text(encoding="utf-8"))
    mapped: list[dict] = []
    unmapped: list[dict] = []
    for slug, alt in sorted(roster.items()):
        cid = PRY_EXPLICIT.get(slug) or name_index.get(norm(alt))
        basis = "explicit" if slug in PRY_EXPLICIT else ("name" if cid else "")
        if cid is None and "(treasure)" in alt.lower():
            cid = name_index.get(norm(re.sub(r"\s*\(treasure\)", "", alt, flags=re.I)))
            basis = "treasure_base" if cid else ""
        if cid is None:
            first = norm(alt).split(":")[0]
            hits = {v for k, v in name_index.items() if k.split(":")[0] == first}
            if len(hits) == 1:
                cid = hits.pop()
                basis = "first_token"
        if cid is None:
            unmapped.append({"slug": slug, "name": alt})
            continue
        playable[cid].add(alt)
        mapped.append({"slug": slug, "name": alt, "id": cid, "basis": basis})
    return mapped, unmapped


def scan_library() -> dict[int, dict]:
    """扫素材库，按基础代号归并。只解析文件名，不读图。"""
    found: dict[int, dict] = {}
    if not LIBRARY_ROOT.is_dir():
        raise SystemExit(f"缺少素材库：{LIBRARY_ROOT}")
    for subdir in LIBRARY_DIRS:
        base = LIBRARY_ROOT / subdir
        if not base.is_dir():
            continue
        for path in base.iterdir():
            if not path.is_file() or path.suffix.lower() != ".png":
                continue
            if subdir == "立绘SI":
                m = SI_RE.match(path.name)
            else:
                m = BARE_RE.match(path.name) or NAME_RE.match(path.name)
            if not m:
                continue
            cid = int(m.group("id"))
            entry = found.setdefault(cid, {"names": set(), "kinds": set(), "variants": set(), "files": 0})
            entry["kinds"].add(KINDS[subdir])
            entry["variants"].add(int(m.group("var")))
            entry["files"] += 1
            if subdir != "立绘SI" and m.groupdict().get("nm"):
                nm = m.group("nm").strip()
                if nm and nm not in SKIP_NAMES and not re.fullmatch(r"c\d+", nm):
                    entry["names"].add(nm)
    return found


def build(cn: dict[int, dict], dict_by_id: dict[int, dict], playable: dict[int, set[str]],
          library: dict[int, dict], locale_fields: dict[int, dict]) -> dict:
    ids = sorted(set(cn) | set(library))
    name_owners: dict[str, list[int]] = defaultdict(list)
    for cid, row in cn.items():
        if row["cnName"]:
            name_owners[norm(row["cnName"])].append(cid)

    records = []
    for cid in ids:
        cn_row = cn.get(cid, {})
        dict_row = dict_by_id.get(cid, {})
        lib = library.get(cid, {"names": set(), "kinds": set(), "variants": set(), "files": 0})
        loc_info = locale_fields.get(cid, {})
        official = cn_row.get("cnName", "")
        lib_names = sorted(lib["names"])
        intl_names = sorted(playable.get(cid, set()))
        issues: list[dict] = []
        recommended = official

        if official:
            # 同名多代号：先看国际服谁是可操作，再看本站位是否只是「只有 name」的占位槽
            owners = name_owners.get(norm(official), [])
            if len(owners) > 1:
                winners = [o for o in owners if o in playable]
                peer_ids = [o for o in owners if o != cid]
                if len(winners) == 1 and winners[0] == cid:
                    verdict = "正主"
                    detail = f"「{official}」同时标注在 {owners}，国际服可操作仅本代号"
                elif loc_info.get("placeholder"):
                    recommended = ""
                    verdict = "错标·占位槽位"
                    detail = (f"「{official}」同时标注在 {owners}；本条 locale 只有 name 字段、无简介无配音，"
                              f"属客户端占位槽，名字是从别的角色复用的")
                elif len(winners) == 1:
                    recommended = ""
                    verdict = "错标·非正主"
                    detail = f"「{official}」与 c{winners[0]:03d} 重名，国际服可操作是后者"
                else:
                    verdict = "待人工裁决"
                    detail = f"「{official}」同时标注在 {owners}，国际服均不可操作，且两处均有文案，无法自动裁决"
                issues.append({"type": "name_conflict", "detail": detail,
                               "verdict": verdict, "peerIds": peer_ids})
            # 素材库名 vs 官方名
            if lib_names:
                for nm in lib_names:
                    if norm(nm) == norm(official):
                        continue
                    if norm(official).startswith(norm(nm)):
                        issues.append({
                            "type": "name_truncated",
                            "detail": f"素材库文件名「{nm}」缺后缀，官方名为「{official}」",
                            "recommendedName": official,
                        })
                    elif norm(nm).startswith(norm(official)):
                        issues.append({
                            "type": "name_extra",
                            "detail": f"素材库文件名「{nm}」比官方名「{official}」多出合称成分（双人立绘等）",
                            "recommendedName": official,
                        })
                    else:
                        issues.append({
                            "type": "name_mismatch",
                            "detail": f"素材库文件名「{nm}」与官方名「{official}」不符",
                            "recommendedName": official,
                        })
            if not lib["kinds"]:
                issues.append({"type": "no_assets", "detail": "素材库无三档资源"})
        else:
            # locale 无此代号：有立绘但客户端没给中文名
            if intl_names:
                issues.append({
                    "type": "no_cn_name",
                    "detail": f"国服 locale 无记录，国际服可操作名：{'／'.join(intl_names)}",
                })
                recommended = dict_row.get("cnName") or ""
            else:
                issues.append({"type": "no_cn_name", "detail": "两源均无名字，按 NPC/未实装立绘池处理"})

        intl_playable = cid in playable
        tier = cn_row.get("tier", "")
        if tier in ("可操作", "可操作-国配缺失"):
            state = "cn_playable"
        elif intl_playable and tier == "预埋":
            state = "intl_playable_cn_preorder"
        elif tier in ("预埋", "NPC"):
            state = "npc_or_unreleased"
        elif intl_playable:
            state = "intl_playable_cn_absent"
        else:
            state = "unknown_library_only"

        records.append({
            "id": cid,
            "code": f"c{cid:03d}",
            "cnName": official,
            "recommendedCnName": recommended,
            "cnNameSource": "cn_locale" if official else ("dictionary" if recommended else "none"),
            "cnTier": tier,
            "localeFields": loc_info.get("fields", 0),
            "placeholder": bool(loc_info.get("placeholder")),
            "intlPlayable": intl_playable,
            "intlNames": intl_names,
            "library": {
                "names": lib_names,
                "kinds": sorted(lib["kinds"]),
                "variants": sorted(lib["variants"]),
                "files": lib["files"],
            },
            "state": state,
            "issues": issues,
        })
    return {"records": records, "nameOwners": {k: v for k, v in name_owners.items() if len(v) > 1}}


def summarize(records: list[dict]) -> dict:
    issue_counter = Counter()
    for r in records:
        for issue in r["issues"]:
            issue_counter[issue["type"]] += 1
    return {
        "totalIds": len(records),
        "states": dict(Counter(r["state"] for r in records)),
        "issues": {k: issue_counter.get(k, 0) for k in
                   ("name_conflict", "name_truncated", "name_extra", "name_mismatch", "no_cn_name", "no_assets")},
        "withCnName": sum(1 for r in records if r["cnName"]),
        "intlPlayable": sum(1 for r in records if r["intlPlayable"]),
        "placeholderSlots": sum(1 for r in records if r["placeholder"]),
    }


STATE_LABEL = {
    "cn_playable": "国服可操作",
    "intl_playable_cn_preorder": "国际服可操作·国服预埋",
    "npc_or_unreleased": "预埋/NPC（国际服亦不可操作）",
    "intl_playable_cn_absent": "国际服可操作·国服无记录",
    "unknown_library_only": "仅素材库有·状态未定",
}
ISSUE_LABEL = {
    "name_conflict": "同名多代号",
    "name_truncated": "名字被截断",
    "name_extra": "名字多出合称",
    "name_mismatch": "名字不符",
    "no_cn_name": "无中文名",
    "no_assets": "无素材",
}
KIND_LABEL = {"avatar": "半身像", "icon": "方图", "portrait": "立绘HD", "compact": "紧裁"}


def write_report(payload: dict, unmapped: list[dict]) -> Path:
    records = payload["records"]
    c = payload["counts"]
    stamp = datetime.now().strftime("%Y%m%d")
    lines = [
        "# 角色代号权威对账（国服 locale × 国际服名单 × 拆包素材库）",
        "",
        f"> 生成：{payload['generatedAt']}　脚本：`scripts/build_character_id_registry.py`",
        "> 判据：国服 locale 定中文名与实装分档；国际服可操作名单定「是否已上线」；素材库只证明资源存在，不证明名字。",
        "",
        "## 1. 总量",
        "",
        f"- 代号总数 **{c['totalIds']}**（国服 locale {len(payload['sources']['cnLocaleIds'])} 条 ∪ 素材库 {sum(1 for r in records if r['library']['kinds'])} 个，交集 {len(set(payload['sources']['cnLocaleIds']) & {r['id'] for r in records if r['library']['kinds']})}）",
        f"- 有中文名 **{c['withCnName']}**，国际服可操作 **{c['intlPlayable']}**",
        "",
        "| 状态 | 数量 |",
        "|---|---|",
    ]
    for key, cnt in sorted(c["states"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {STATE_LABEL.get(key, key)} | {cnt} |")
    lines += ["", "| 异常 | 数量 |", "|---|---|"]
    for key, cnt in c["issues"].items():
        lines.append(f"| {ISSUE_LABEL.get(key, key)} | {cnt} |")

    placeholders = [r for r in records if r["placeholder"]]
    lines += [
        "",
        "## 1.1 根因：客户端占位槽",
        "",
        f"国服 locale 里有 **{c['placeholderSlots']}** 个代号**只填了 `name` 一个字段**，"
        "没有简介、没有国配、没有看板或战斗语音 —— 那是客户端预留的 id 槽位，"
        "名字直接从别的角色复制过来占位。素材库命名时照抄 locale，于是错误向下传导。",
        "",
        "对照：真角色 c514（格拉维）22 个字段、c260（神罚）38 个字段；"
        "被错标的 c510、c915、c930 都只有 1 个字段。",
        "",
        "| 代号 | locale 字段数 | 现用名 | 分档 | 国际服可操作 |",
        "|---|---|---|---|---|",
    ]
    for r in placeholders:
        lines.append(f"| c{r['id']:03d} | {r['localeFields']} | {r['cnName'] or '—'} | {r['cnTier']} | "
                     f"{'是' if r['intlPlayable'] else '否'} |")
    lines += [
        "",
        "> 占位槽不一定错 —— 国际服可操作的那些（c182、c223、c331、c834–c842 等）是国服只预埋了名字，"
        "名字本身可信。**只有在「占位槽 + 与真角色重名 + 国际服不可操作」三条同时成立时才判定错标。**",
    ]

    lines += ["", "## 2. 同名多代号（汉化污染源）", "",
              "同一中文名被贴到多个代号上，用国际服是否可操作、英文名是否唯一来裁决。", "",
              "| 代号 | 官方名 | 分档 | locale 完整度 | 国际服可操作 | 国际服名 | 处置 |", "|---|---|---|---|---|---|---|"]
    for r in records:
        if not any(i["type"] == "name_conflict" for i in r["issues"]):
            continue
        verdict = next(i["verdict"] for i in r["issues"] if i["type"] == "name_conflict")
        fields = f"{r['localeFields']} 字段" + ("·占位槽" if r["placeholder"] else "")
        lines.append(
            f"| c{r['id']:03d} | {r['cnName']} | {r['cnTier']} | {fields} | {'是' if r['intlPlayable'] else '否'} | "
            f"{'／'.join(r['intlNames']) or '—'} | {verdict} |"
        )

    lines += ["", "## 3. 素材库文件名与官方名不一致", "",
              "| 代号 | 素材库文件名 | 官方名 | 类型 |", "|---|---|---|---|"]
    for r in records:
        for issue in r["issues"]:
            if issue["type"] in ("name_truncated", "name_extra", "name_mismatch"):
                lines.append(f"| c{r['id']:03d} | {'／'.join(r['library']['names'])} | {r['cnName']} | {ISSUE_LABEL[issue['type']]} |")

    lines += ["", "## 4. 国际服可操作但国服未开放", "",
              "国服 locale 有名字但分档为「预埋」，国际服已是可操作角色 —— 未来版本会进卡池。", "",
              "| 代号 | 官方名 | 国际服名 |", "|---|---|---|"]
    for r in records:
        if r["state"] == "intl_playable_cn_preorder":
            lines.append(f"| c{r['id']:03d} | {r['cnName']} | {'／'.join(r['intlNames'])} |")

    lines += ["", "## 5. 客户端有立绘但无中文名", "",
              f"共 {c['issues']['no_cn_name']} 个代号。国际服可操作的按国际服名回填，其余按 NPC 立绘池处理。", "",
              "| 代号 | 素材档位 | 国际服可操作 | 国际服名 | 建议中文名 |", "|---|---|---|---|---|"]
    for r in records:
        if r["cnName"]:
            continue
        lines.append(
            f"| c{r['id']:03d} | {'/'.join(KIND_LABEL.get(k, k) for k in r['library']['kinds']) or '—'} | "
            f"{'是' if r['intlPlayable'] else '否'} | {'／'.join(r['intlNames']) or '—'} | {r['recommendedCnName'] or '—'} |"
        )

    if unmapped:
        lines += ["", "## 6. prydwen 名单未能映射的条目", "", "| slug | 英文名 |", "|---|---|"]
        for row in unmapped:
            lines.append(f"| {row['slug']} | {row['name']} |")

    lines += ["", "## 7. 修复动作", "",
              "**已自动修复**（脚本 `scripts/fix_library_names.py`，流水见 `回收站/library_rename_*.json`）：",
              "",
              "- 双前缀命名 bug 79 个文件：`c917_c917_00_mi_uc_tex.png` -> `c917_00_mi_uc_tex.png`",
              "- 名字截断：`灰姑娘_c515_00_*` -> `灰姑娘：琉璃波光_c515_00_*`（官方名 `515_name`）",
              "- 索引表 `00_索引/角色代号中文名对照表.xlsx` 同步 4 行（515/510/915/930）",
              "- 索引表 `00_索引/图片多规格对照表.xlsx` 同步 316 个 `01_角色` 路径单元格（`06_骨骼` 等未改名的目录保持原样）",
              "",
              "**保留未改**：",
              "",
              "- `布兰儿&诺亚尔_c271_*`：立绘画的是两个人，有信息量，仅在对账表里写明官方名是「诺亚尔」",
              "",
              "**待人工看图定名**：",
              "",
              "- c510（格拉维占位槽，另一套造型）、c930（E.H. 占位槽，图上是一只动物）",
              "- c890 / c908 同名字节相同的立绘，疑似同一角色的重复槽位，需确认留哪个",
              "",
              "## 8. 产物", "",
              "- `data/character_id_registry.json`：代号主表，含官方名、分档、locale 字段数、占位槽标记、国际服状态、素材档位、异常清单",
              "- 本报告：`核心目录/报告/角色id权威对账_" + stamp + ".md`",
              ""]
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"角色id权威对账_{stamp}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="建立角色代号权威主表并裁决汉化冲突")
    parser.add_argument("--apply", action="store_true", help="写入主表与报告")
    args = parser.parse_args()

    cn = load_cn_roster()
    dict_by_id, dict_by_name = load_dictionary()
    playable, name_index = load_intl()
    mapped, unmapped = map_prydwen(playable, name_index)
    library = scan_library()
    locale_fields = load_locale_fields()
    built = build(cn, dict_by_id, playable, library, locale_fields)
    counts = summarize(built["records"])
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rules": {
            "cnName": "国服 locale `Locale_Character.lss` 的 name 字段，唯一权威",
            "cnTier": "可操作 = 有国配 + 有看板/好感语音；预埋 = 只有 name；NPC = 有配音无看板语音",
            "intlPlayable": "Nikke.gg 快照 + prydwen 可操作名单（prydwen 只收可操作角色）",
            "library": "拆包素材库只证明资源存在，不作为名字依据",
        },
        "sources": {
            "cnLocale": str(CN_ROSTER.relative_to(ROOT)).replace("\\", "/"),
            "cnLocaleDb": str(LOCALE_DB.relative_to(ROOT)).replace("\\", "/"),
            "cnLocaleIds": sorted(cn),
            "dictionary": str(DICTIONARY.relative_to(ROOT)).replace("\\", "/"),
            "ggRoster": str(GG_ROSTER.relative_to(ROOT)).replace("\\", "/"),
            "prydwen": str(PRY_CACHE.relative_to(ROOT)).replace("\\", "/"),
            "library": str(LIBRARY_ROOT),
            "prydwenMapped": len(mapped),
            "prydwenUnmapped": unmapped,
        },
        "counts": counts,
        "nameOwners": built["nameOwners"],
        "records": built["records"],
    }

    print(f"代号 {counts['totalIds']}　有中文名 {counts['withCnName']}　国际服可操作 {counts['intlPlayable']}"
          f"　占位槽 {counts['placeholderSlots']}")
    for key, cnt in sorted(counts["states"].items(), key=lambda kv: -kv[1]):
        print(f"  {STATE_LABEL.get(key, key):28s} {cnt}")
    print("异常：" + "　".join(f"{ISSUE_LABEL[k]} {v}" for k, v in counts["issues"].items()))
    print(f"prydwen 映射 {len(mapped)} / 未映射 {len(unmapped)}")

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 生成主表与报告。")
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    report = write_report(payload, unmapped)
    print(f"\n已写入 {OUT_JSON}")
    print(f"已写入 {report}")


if __name__ == "__main__":
    main()
