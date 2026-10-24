"""把素材库文件名里的中文名对齐到权威主表，并修掉双前缀命名 bug。

只做两类**确定性**修改：
  1) `cXXX_cXXX_00_*` -> `cXXX_00_*`
     命名脚本把代号当成中文名又拼了一次，属于纯 bug。
  2) 文件名中文名与官方名不一致 -> 换成官方名
     官方名来源：`data/character_id_registry.json` 的 `cnName`（国服 locale）。

不改的部分：
  - 占位槽错标（c510 / c915 / c930 这类）：国服 locale 只有 name 一个字段，
    名字是从别的角色复用的，没有权威名可依，必须人工看图定名。
  - 双人合称（c271「布兰儿&诺亚尔」）：立绘本身画了两个人，改名会丢信息。

用法：
    python scripts/fix_library_names.py            # 只打印计划
    python scripts/fix_library_names.py --apply    # 备份后执行改名
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "character_id_registry.json"
LIBRARY_ROOT = Path(r"F:\Codex\Nikke\Nikke_Skills\拆包\00_资源库\01_角色")
TRASH = ROOT / "回收站"
DIRS = ("头像", "立绘HD", "立绘")

DUP_PREFIX = re.compile(r"^c0*(\d+)_c0*(\d+)_(?P<rest>.+)$")
NAME_RE = re.compile(r"^(?:(?P<nm>.+?)_)?c0*(?P<id>\d+)_(?P<var>\d+)_(?P<rest>.+)$")
SKIP_NAMES = {"si", "mi", "sd"}


def norm(text: str) -> str:
    if not text:
        return ""
    table = str.maketrans({"：": ":", "．": ".", "（": "(", "）": ")", "　": ""})
    return re.sub(r"[\s&・]", "", text.translate(table)).lower()


def load_official() -> dict[int, str]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {r["id"]: r["cnName"] for r in payload["records"] if r.get("cnName")}


def plan() -> tuple[list[dict], list[dict]]:
    official = load_official()
    fixes: list[dict] = []
    skipped: list[dict] = []
    for subdir in DIRS:
        base = LIBRARY_ROOT / subdir
        if not base.is_dir():
            continue
        for path in sorted(base.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".png":
                continue

            # ① 双前缀：cXXX_cXXX_00_*.png -> cXXX_00_*.png
            m = DUP_PREFIX.match(path.name)
            if m:
                target = base / f"c{int(m.group(1)):03d}_{m.group('rest')}"
                fixes.append({"kind": "dedupe_prefix", "dir": subdir,
                              "src": path.name, "dst": target.name})
                continue

            # ② 中文名与官方名不一致
            m = NAME_RE.match(path.name)
            if not m or not m.group("nm"):
                continue
            current = m.group("nm").strip()
            if current in SKIP_NAMES or re.fullmatch(r"c\d+", current):
                continue
            cid = int(m.group("id"))
            want = official.get(cid)
            if not want:
                continue
            if norm(want) == norm(current):
                continue
            if norm(want) in norm(current):
                skipped.append({"kind": "alias_longer", "dir": subdir, "src": path.name,
                                "official": want, "note": "文件名比官方名长（双人合称等），保留"})
                continue
            target = base / f"{want}_c{cid:03d}_{int(m.group('var')):02d}_{m.group('rest')}"
            fixes.append({"kind": "rename_to_official", "dir": subdir,
                          "src": path.name, "dst": target.name, "official": want})
    return fixes, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="修正素材库文件名中文名")
    parser.add_argument("--apply", action="store_true", help="备份后执行改名")
    args = parser.parse_args()

    if not REGISTRY.is_file():
        raise SystemExit(f"缺少权威主表：{REGISTRY}（先跑 build_character_id_registry.py --apply）")

    fixes, skipped = plan()
    by_kind: dict[str, int] = {}
    for item in fixes:
        by_kind[item["kind"]] = by_kind.get(item["kind"], 0) + 1
    print(f"待改名 {len(fixes)} 个文件：{by_kind}")
    for item in fixes[:40]:
        print(f"  [{item['dir']}] {item['src']}")
        print(f"      -> {item['dst']}")
    if len(fixes) > 40:
        print(f"  …… 其余 {len(fixes) - 40} 条略")
    if skipped:
        print(f"\n保留 {len(skipped)} 个：")
        for item in skipped:
            print(f"  [{item['dir']}] {item['src']} -> 官方「{item['official']}」（{item['note']}）")

    if not args.apply:
        print("\n[dry-run] 未改动任何文件。加 --apply 执行。")
        return

    TRASH.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    journal = TRASH / f"library_rename_{stamp}.json"
    done: list[dict] = []
    failed: list[dict] = []
    for item in fixes:
        src = LIBRARY_ROOT / item["dir"] / item["src"]
        dst = LIBRARY_ROOT / item["dir"] / item["dst"]
        if not src.is_file():
            failed.append({**item, "reason": "源文件不存在"})
            continue
        if dst.exists():
            failed.append({**item, "reason": "目标文件已存在"})
            continue
        try:
            shutil.move(str(src), str(dst))
            done.append(item)
        except OSError as exc:
            failed.append({**item, "reason": f"{type(exc).__name__}: {exc}"})
    journal.write_text(json.dumps({"appliedAt": stamp, "done": done, "failed": failed},
                                  ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n已改名 {len(done)}　失败 {len(failed)}")
    print(f"改名流水：{journal}")
    for item in failed:
        print(f"  失败 [{item['dir']}] {item['src']}：{item['reason']}")


if __name__ == "__main__":
    main()
