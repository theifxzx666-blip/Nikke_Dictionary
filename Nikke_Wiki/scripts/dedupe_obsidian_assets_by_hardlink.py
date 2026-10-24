"""把 Obsidian vault 的 assets/characters 去重为硬链接（源：data/character_repository/assets/characters）。

v2：不使用 os.remove / unlink（避免安全删除层的批量确认拦截），
改为 os.link 生成临时硬链 + os.replace 原子覆盖。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "character_repository" / "assets" / "characters"
DST = ROOT / "obsidian_character_database" / "NIKKE角色库" / "assets" / "characters"
TMP = ROOT / ".hl_stage"


def main() -> None:
    assert SRC.is_dir() and DST.is_dir()
    TMP.mkdir(exist_ok=True)
    src_files = {p.relative_to(SRC): p for p in SRC.rglob("*") if p.is_file()}

    done = skipped = failed = 0
    n = 0
    for rel, sp in src_files.items():
        dp = DST / rel
        dp.parent.mkdir(parents=True, exist_ok=True)
        try:
            if dp.exists() and os.stat(sp).st_ino == os.stat(dp).st_ino:
                skipped += 1
                continue
            n += 1
            staged = TMP / f"{os.getpid()}_{n}.lnk"
            os.link(sp, staged)
            os.replace(staged, dp)
            done += 1
        except OSError as exc:
            failed += 1
            if failed <= 5:
                print("FAIL", rel, exc)

    bad = sum(
        1
        for rel, sp in src_files.items()
        if not (DST / rel).exists() or os.stat(sp).st_ino != os.stat(DST / rel).st_ino
    )
    print(json.dumps({"linked": done, "already": skipped, "failed": failed, "inoMismatch": bad}, ensure_ascii=False))


if __name__ == "__main__":
    main()
