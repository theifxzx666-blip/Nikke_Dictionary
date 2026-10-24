"""Local receiver for browser-collected GameKee event stories."""
from __future__ import annotations
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BATCH_DIR = Path()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            slug = str(payload.get("slug", ""))
            series = payload.get("series")
            if not slug or not isinstance(series, dict) or "/" in slug or "\\" in slug:
                raise ValueError("invalid payload")
            target = BATCH_DIR / f"{slug}.json"
            if target.exists():
                previous = json.loads(target.read_text(encoding="utf-8"))
                old = (previous.get("series") or [{}])[0]
                episodes = {x.get("number"): x for x in old.get("episodes", [])}
                episodes.update({x.get("number"): x for x in series.get("episodes", [])})
                series = dict(series)
                series["episodes"] = [episodes[k] for k in sorted(episodes) if k is not None]
                series["warnings"] = sorted(set(old.get("warnings", [])) | set(series.get("warnings", [])))
            BATCH_DIR.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".partial.json")
            tmp.write_text(json.dumps({"sourceUrl": payload.get("sourceUrl", ""), "retrievedAt": payload.get("retrievedAt", ""), "series": [series]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            tmp.replace(target)
            self.send_response(204)
        except Exception as exc:  # noqa: BLE001
            self.send_response(400); self.end_headers(); self.wfile.write(str(exc).encode("utf-8")); return
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return

def main() -> None:
    global BATCH_DIR
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8766); parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args(); BATCH_DIR = Path(args.batch_dir)
    print(f"event receiver listening on http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()

if __name__ == "__main__":
    main()
