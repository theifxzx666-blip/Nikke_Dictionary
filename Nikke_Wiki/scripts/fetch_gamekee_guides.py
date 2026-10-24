"""采集 GameKee 玩法/机制攻略页，落成可检索的纯文本快照。

与 `enrich_gamekee_character_assets.py`（角色卡）分开，因为两类页面结构不同：
角色页是「表格 baseData」，攻略页多数是「富文本节点列表」（header/paragraph/image）。

产物：
  cache/gamekee_guide_details/content_<cid>.json   原始快照（含 content_cdn 与抓取时间）
  data/gamekee_guides/guides.jsonl                 规范化正文（一行一页）
  data/reports/gamekee_guide_fetch_report.json     抓取报告

用法：
  python scripts/fetch_gamekee_guides.py            # dry-run，只探测不写盘
  python scripts/fetch_gamekee_guides.py --write    # 真抓并写盘
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "cache" / "gamekee_guide_details"
OUT_DIR = PROJECT_ROOT / "data" / "gamekee_guides"
REPORT = PROJECT_ROOT / "data" / "reports" / "gamekee_guide_fetch_report.json"
TREE_CACHE = PROJECT_ROOT / "data" / "gamekee_entry_tree.json"

API = "https://www.gamekee.com/v1"
CDN = "https://cdnimg-v2.gamekee.com/"
GAME_ID = 64581

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json,text/plain,*/*",
    "X-Requested-With": "XMLHttpRequest",
    "game-alias": "nikke",
    "Lang": "zh-cn",
    "device-num": "1",
    "Referer": "https://www.gamekee.com/nikke/",
}

# 不要的整类栏目：角色图鉴/地图收集/角色测评/美术/招募/活动存档/小游戏/过时攻略。
# 角色资料已由 charcards 走角色页单独采，重复采会污染检索。
EXCLUDE_PATH = (
    "妮姬图鉴",
    "地图收集",
    "角色测评",
    "图文测评",
    "美术资源",
    "招募专区",
    "活动存档",
    "活动小游戏",
    "过时攻略",
    "采访合集",
)

# 纯服务信息（装什么加速器、CDK 去哪领、账号充值），与游戏知识无关
EXCLUDE_NAME = (
    "安装教学",
    "新手FAQ",
    "封号申诉",
    "模拟器推荐",
    "手机横屏",
    "友情Q群",
    "充值账号推荐",
    "加速器推荐",
    "反和谐教学",
    "数据转移",
    "游戏测评",
    "企划",
)


def request_json(url: str, retries: int = 3) -> dict:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8-sig"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"请求失败 {url}: {last}")


def request_bytes(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={**HEADERS, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(1.2 * (i + 1))
    raise RuntimeError(f"下载失败 {url}: {last}")


def cdn_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    return url.replace("https://api-cdn.gamekee.com/", CDN)


# ---------------------------------------------------------------- 目录树


def fetch_tree() -> list[dict]:
    """递归抓整棵目录树，返回扁平节点列表（含 path）。"""
    out: list[dict] = []

    def walk(pid: int | None, path: list[str], depth: int) -> None:
        if depth > 4:
            return
        url = f"{API}/entry/treesByPid?pid={pid}"
        nodes = request_json(url).get("data") or []
        for n in nodes:
            name = (n.get("name") or "").strip()
            if not name:
                continue
            p = path + [name]
            out.append(
                {
                    "id": n.get("id"),
                    "name": name,
                    "path": " / ".join(p),
                    "type": n.get("type"),
                    "content_id": n.get("content_id") or 0,
                    "jump_url": n.get("jump_url") or "",
                    "is_third": n.get("is_third"),
                }
            )
            if n.get("type") == 1 and not n.get("content_id"):
                walk(int(n["id"]), p, depth + 1)

    tops = request_json(f"{API}/entry/treesByPid?game_id={GAME_ID}").get("data") or []
    for n in tops:
        name = (n.get("name") or "").strip()
        out.append(
            {
                "id": n.get("id"),
                "name": name,
                "path": name,
                "type": n.get("type"),
                "content_id": n.get("content_id") or 0,
                "jump_url": n.get("jump_url") or "",
                "is_third": n.get("is_third"),
            }
        )
        walk(int(n["id"]), [name], 1)
    return out


def pick_targets(tree: list[dict]) -> list[dict]:
    out = []
    for t in tree:
        if not t["content_id"] or t["type"] != 1:
            continue
        if any(x in t["path"] for x in EXCLUDE_PATH):
            continue
        if any(x == t["name"] or x in t["name"] for x in EXCLUDE_NAME):
            continue
        out.append(t)
    return out


# ---------------------------------------------------------------- 正文解析


def _node_text(node: object, out: list[str], images: list[str]) -> None:
    """把富文本节点摊平成文本行。标题单独成行，图片只记 URL 计数。"""
    if isinstance(node, list):
        for n in node:
            _node_text(n, out, images)
        return
    if not isinstance(node, dict):
        return

    ntype = str(node.get("type") or "")
    if ntype == "image" or node.get("src"):
        src = cdn_url(str(node.get("src") or ""))
        if src:
            images.append(src)
        return

    buf: list[str] = []

    def collect(n: object) -> None:
        if isinstance(n, dict):
            if str(n.get("type") or "") == "image" or (n.get("src") and not n.get("text")):
                src = cdn_url(str(n.get("src") or ""))
                if src:
                    images.append(src)
                return
            if n.get("text"):
                buf.append(str(n["text"]))
            for c in n.get("children") or []:
                collect(c)
        elif isinstance(n, list):
            for c in n:
                collect(c)

    collect(node)
    line = "".join(buf).replace("\u00a0", " ").strip()
    if not line:
        return
    if ntype.startswith("header"):
        level = ntype[-1] if ntype[-1].isdigit() else "2"
        out.append("#" * min(int(level) + 1, 6) + " " + line)
    elif ntype in ("list", "listitem"):
        out.append("- " + line)
    else:
        out.append(line)


def _html_to_text(html: str) -> tuple[str, int]:
    """老页面（type=4/15）的正文是 HTML 字符串，摊平成带标题层级的文本。"""

    class _P(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.lines: list[str] = []
            self.images: list[str] = []
            self.buf: list[str] = []
            self.head = 0
            self.cell: list[str] | None = None
            self.row: list[str] = []
            self.skip = 0

        def _flush(self) -> None:
            text = "".join(self.buf).strip()
            self.buf = []
            if not text:
                return
            if self.head:
                self.lines.append("#" * min(self.head + 1, 6) + " " + text)
            else:
                self.lines.append(text)

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            a = {k: (v or "") for k, v in attrs}
            if tag in ("script", "style"):
                self.skip += 1
            elif tag in ("h1", "h2", "h3", "h4", "h5"):
                self._flush()
                self.head = int(tag[1])
            elif tag == "img":
                src = cdn_url(a.get("src") or a.get("data-src") or "")
                if src:
                    self.images.append(src)
            elif tag == "br":
                self._flush()
            elif tag == "tr":
                self._flush()
                self.row = []
            elif tag in ("td", "th"):
                self.cell = []
            elif tag == "li":
                self._flush()
                self.buf.append("- ")

        def handle_endtag(self, tag: str) -> None:
            if tag in ("script", "style"):
                self.skip = max(0, self.skip - 1)
            elif tag in ("h1", "h2", "h3", "h4", "h5"):
                self._flush()
                self.head = 0
            elif tag in ("td", "th") and self.cell is not None:
                self.row.append("".join(self.cell).strip())
                self.cell = None
            elif tag == "tr":
                cells = [c for c in self.row if c]
                if cells:
                    self.lines.append(" ｜ ".join(cells))
                self.row = []
            elif tag in ("p", "div", "li", "table", "ul", "ol", "blockquote"):
                self._flush()

        def handle_data(self, data: str) -> None:
            if self.skip:
                return
            if self.cell is not None:
                self.cell.append(data)
            else:
                self.buf.append(data)

    p = _P()
    p.feed(html)
    p._flush()
    return "\n".join(ln for ln in p.lines if ln.strip()), len(p.images)


def parse_body(raw: bytes) -> tuple[str, int]:
    """返回 (正文, 图片数)。兼容三种形态：富文本节点列表 / 表格 baseData / HTML 字符串。"""
    doc = json.loads(raw.decode("utf-8-sig"))
    content = doc.get("content")

    if isinstance(content, str):
        head = content.lstrip()[:1]
        if head in ("<",):
            return _html_to_text(content)
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return _html_to_text(content)

    images: list[str] = []
    lines: list[str] = []

    if isinstance(content, list):
        _node_text(content, lines, images)
    elif isinstance(content, dict) and content.get("baseData"):
        for row in content["baseData"]:
            cells: list[str] = []
            for cell in row or []:
                if not isinstance(cell, dict):
                    continue
                if cell.get("type") == "image" and cell.get("value"):
                    images.append(cdn_url(str(cell["value"])))
                    continue
                val = str(cell.get("value") or "").strip()
                if val:
                    cells.append(val)
            if cells:
                lines.append(" ｜ ".join(cells))

    # 压掉连续空行，保留段落分隔
    tidy: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        tidy.append(ln)
    return "\n".join(tidy), len(images)


# ---------------------------------------------------------------- 主流程


def gather(targets: list[dict], *, write: bool, sleep: float) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetched: list[dict] = []
    failed: list[dict] = []

    for i, t in enumerate(targets, 1):
        cid = int(t["content_id"])
        page_url = f"https://www.gamekee.com/nikke/{cid}.html"
        cache_path = CACHE_DIR / f"content_{cid}.json"
        try:
            if cache_path.exists():
                raw = cache_path.read_bytes()
                cached = True
            else:
                detail = request_json(f"{API}/content/detail/{cid}")
                cdn = (detail.get("data") or {}).get("content_cdn") or ""
                if not cdn:
                    raise RuntimeError("没有 content_cdn")
                try:
                    raw = request_bytes(cdn_url(cdn))
                except RuntimeError:
                    # 少数老页只在 api-cdn 上有文件，回退原始 host 再试一次
                    raw = request_bytes(cdn_url(cdn).replace(CDN, "https://api-cdn.gamekee.com/"))
                if write:
                    cache_path.write_bytes(raw)
                cached = False
                time.sleep(sleep)
            text, n_img = parse_body(raw)
            fetched.append(
                {
                    "content_id": cid,
                    "title": t["name"],
                    "path": t["path"],
                    "url": page_url,
                    "chars": len(text),
                    "images": n_img,
                    "hash": hashlib.sha1(raw).hexdigest()[:16],
                    "cached": cached,
                    "text": text,
                }
            )
            print(
                f"[{i:>3}/{len(targets)}] {t['name'][:22]:<24} "
                f"{len(text):>6}字 {n_img:>3}图 {'缓存' if cached else '新抓'}"
            )
        except Exception as exc:  # noqa: BLE001  采集器要吞掉单页失败，继续下一页
            failed.append({"content_id": cid, "title": t["name"], "path": t["path"], "error": str(exc)})
            print(f"[{i:>3}/{len(targets)}] {t['name'][:22]:<24} 失败：{exc}")

    if write and fetched:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with (OUT_DIR / "guides.jsonl").open("w", encoding="utf-8") as f:
            for rec in fetched:
                f.write(json.dumps({**rec, "fetched_at": now}, ensure_ascii=False) + "\n")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(
            json.dumps(
                {
                    "fetched_at": now,
                    "pages": len(fetched),
                    "failed": failed,
                    "total_chars": sum(r["chars"] for r in fetched),
                    "total_images": sum(r["images"] for r in fetched),
                    "items": [
                        {k: r[k] for k in ("content_id", "title", "path", "url", "chars", "images", "hash")}
                        for r in fetched
                    ],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )

    return {
        "pages": len(fetched),
        "failed": failed,
        "total_chars": sum(r["chars"] for r in fetched),
        "thin": [r for r in fetched if r["chars"] < 300],
        "fetched": fetched,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真抓并写盘（默认 dry-run）")
    ap.add_argument("--sleep", type=float, default=0.35, help="请求间隔秒")
    ap.add_argument("--refresh-tree", action="store_true", help="重新抓目录树")
    args = ap.parse_args()

    if TREE_CACHE.exists() and not args.refresh_tree:
        tree = json.loads(TREE_CACHE.read_text(encoding="utf-8"))
        print(f"[tree] 用缓存 {len(tree)} 节点")
    else:
        tree = fetch_tree()
        TREE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TREE_CACHE.write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[tree] 新抓 {len(tree)} 节点")

    targets = pick_targets(tree)
    print(f"[plan] 目标 {len(targets)} 页  模式={'写入' if args.write else 'dry-run'}")

    res = gather(targets, write=args.write, sleep=args.sleep)
    thin = res["thin"]
    print(
        f"\n[结果] {res['pages']} 页 / {res['total_chars'] // 1024}KB 正文 / "
        f"失败 {len(res['failed'])} / 正文不足 300 字的 {len(thin)} 页"
    )
    if thin:
        print("  偏薄的页（多为纯图攻略，文本库收不到东西）：")
        for r in thin[:20]:
            print(f"    {r['chars']:>5}字 {r['images']:>3}图 {r['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
