"""Local receiver used by the browser side-story collector for immediate JSON saves."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "data" / "plot" / "side_stories" / "batches"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            slug = str(payload.get("slug", ""))
            series = payload.get("series")
            if not slug or not isinstance(series, dict) or "/" in slug or "\\" in slug:
                raise ValueError("invalid payload")
            BATCH_DIR.mkdir(parents=True, exist_ok=True)
            target = BATCH_DIR / f"{slug}.json"
            temporary = target.with_suffix(".partial.json")
            target_series = series
            if target.exists():
                previous = json.loads(target.read_text(encoding="utf-8"))
                previous_series = (previous.get("series") or [{}])[0]
                by_number = {item.get("number"): item for item in previous_series.get("episodes", [])}
                by_number.update({item.get("number"): item for item in series.get("episodes", [])})
                target_series = dict(series)
                target_series["episodes"] = [by_number[key] for key in sorted(by_number) if key is not None]
                target_series["warnings"] = sorted(set(previous_series.get("warnings", [])) | set(series.get("warnings", [])))
            document = {"sourceUrl": payload.get("sourceUrl", ""), "retrievedAt": payload.get("retrievedAt", ""), "series": [target_series]}
            temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(target)
            self.send_response(204)
        except Exception as exc:  # noqa: BLE001
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"side-story receiver listening on http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
