"""Replace incorrectly derived avatars for explicitly identified characters."""

import argparse
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DICTIONARY = DATA / "nikke_character_dictionary_enhanced.json"
BACKUPS = DATA / "character_library_backups"

REPAIRS = {
    "gamekee-711133": "F:/Codex/Nikke/Nikke_Wiki/assets/gamekee_character_assets/playable_form_cards/711133.png",
    "gamekee-711739": "F:/Codex/Nikke/Nikke_Wiki/assets/gamekee_character_assets/playable_form_cards/711739.png",
    "queen-makoto": "F:/Codex/Nikke/Nikke_Wiki/assets/gamekee_character_assets/team_cards/queen-makoto.png",
    "yukiko": "F:/Codex/Nikke/Nikke_Wiki/assets/gamekee_character_assets/team_cards/yukiko.png",
    "aigis": "F:/Codex/Nikke/Nikke_Wiki/assets/gamekee_character_assets/team_cards/aigis.png",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair explicitly identified character avatars")
    parser.add_argument("--apply", action="store_true", help="write dictionary changes")
    args = parser.parse_args()
    rows = json.loads(DICTIONARY.read_text(encoding="utf-8"))
    changes = []
    for row in rows:
        slug = row.get("url", "")
        source = REPAIRS.get(slug)
        if not source:
            continue
        exists = Path(source).is_file()
        changes.append({"slug": slug, "name": row.get("name", ""), "source": source, "exists": exists})
        if args.apply and exists:
            row["localIconFile"] = source
            row["avatarSource"] = "GameKee"
            row["avatarStatus"] = "available"
            row["avatarRepairBasis"] = "用户指出原头像误用全身立绘；改用 GameKee 角色卡素材"
    report = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "apply": args.apply, "changes": changes}
    if args.apply and changes:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        backup = BACKUPS / f"nikke_character_dictionary_enhanced_{time.strftime('%Y%m%d_%H%M%S')}_before_avatar_repair.json"
        shutil.copy2(DICTIONARY, backup)
        DICTIONARY.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["backup"] = str(backup)
    report_path = DATA / "character_repository" / "reports" / ("avatar_repair_latest.json" if args.apply else "avatar_repair_dry_run.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
