from __future__ import annotations

import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"


def show_file(path: Path) -> None:
    raw = path.read_bytes()
    print(path.name, "bytes", len(raw), "head", raw[:80])
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        print("json error", repr(exc))
        print(raw[:300].decode("utf-8", errors="replace"))
        return
    print("json type", type(data).__name__)
    print(json.dumps(data, ensure_ascii=True, indent=2)[:4000])


def search_js() -> None:
    s = (CACHE_DIR / "gamekee_main.js").read_text(encoding="utf-8", errors="ignore")
    for pat in [
        "entry_filter",
        "entryFilter",
        "/v1/entryFilter",
        "/v1/entryKeywordDict",
        "/v1/entryMod",
        "entry_data_bind",
        "entryBind",
    ]:
        print("\\nPAT", pat, "count", s.count(pat))
        for match in re.finditer(re.escape(pat), s):
            start = max(0, match.start() - 700)
            end = min(len(s), match.start() + 900)
            print(s[start:end])
            break


if __name__ == "__main__":
    show_file(DATA_DIR / "gamekee_entry_bind_data.json")
    search_js()
