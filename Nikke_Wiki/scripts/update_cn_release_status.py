import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DICTIONARY = DATA_DIR / "nikke_character_dictionary_enhanced.json"
NAMES_FILE = DATA_DIR / "cn_released_names.txt"
STATUS_FILE = DATA_DIR / "cn_release_status.json"
REPORT_FILE = DATA_DIR / "reports" / "cn_release_status_update_report.json"


def main() -> None:
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    names = [line.strip() for line in NAMES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]

    lookup: dict[str, list[str]] = {}
    for row in rows:
        candidates = {row.get("name", ""), row.get("cnName", ""), row.get("gamekeeCnName", "")}
        candidates.update(x for x in row.get("aliases", "").split("|") if x)
        for candidate in candidates:
            if candidate:
                lookup.setdefault(candidate, []).append(row["name"])

    matched: dict[str, str] = {}
    unmatched: list[str] = []
    ambiguous: dict[str, list[str]] = {}

    for cn_name in names:
        english_names = sorted(set(lookup.get(cn_name, [])))
        if not english_names:
            unmatched.append(cn_name)
        elif len(english_names) > 1:
            ambiguous[cn_name] = english_names
            matched[english_names[0]] = cn_name
        else:
            matched[english_names[0]] = cn_name

    status = {
        "_schema": {
            "status_values": ["已上线", "未上线", "待确认"],
            "fields": ["status", "date", "basis", "note"],
            "description": "国服上线状态独立维护；不要用 GameKee/Nikke.gg 是否有资料直接推断。",
        }
    }
    for english_name, cn_name in sorted(matched.items()):
        status[english_name] = {
            "status": "已上线",
            "date": "",
            "basis": "用户提供的国服已上线名单",
            "note": f"匹配中文名：{cn_name}",
        }

    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(
        json.dumps(
            {
                "inputCount": len(names),
                "matchedCount": len(matched),
                "unmatched": unmatched,
                "ambiguous": ambiguous,
                "matched": matched,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "input": len(names),
                "matched": len(matched),
                "unmatched": unmatched,
                "ambiguous": ambiguous,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
