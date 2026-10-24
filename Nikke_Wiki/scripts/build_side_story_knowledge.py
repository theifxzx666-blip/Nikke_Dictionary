"""Merge saved GameKee side-story batches and build one AstrBot upload document."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLOT_DIR = ROOT / "data" / "plot"
SIDE_DIR = PLOT_DIR / "side_stories"
BATCH_DIR = SIDE_DIR / "batches"
INDEX = SIDE_DIR / "side_story_index.json"
RETRY_QUEUE = SIDE_DIR / "retry_queue.json"
MAIN_INDEX = PLOT_DIR / "main_story_index.json"
BOT_ROOT = Path(r"F:\\Codex\\Nikke\\Nikke_Bot\\knowledge_base")
OUTPUT = BOT_ROOT / "astrbot_upload" / "13_番外剧情_已采集章节.md"
REPORT = ROOT / "核心目录" / "报告" / "side_story_sync_report.md"
CATALOG_URL = "https://www.gamekee.com/nikke/plot/catalog"


def source_text(value: object) -> str:
    return str(value.get("text", "")).strip() if isinstance(value, dict) else str(value or "").strip()


def episode_error(episode: dict, seen_numbers: set[object], seen_urls: set[str], all_urls: set[str]) -> str:
    if not episode.get("title"):
        return "missing_title"
    url = str(episode.get("url", ""))
    if not url.startswith("https://www.gamekee.com/nikke/plot/play/"):
        return "invalid_source_url"
    if not str(episode.get("dialogue", "")).strip():
        return "missing_dialogue"
    if episode.get("number") in seen_numbers:
        return "duplicate_episode_number"
    if url in seen_urls or url in all_urls:
        return "duplicate_source_url"
    return ""


def main() -> None:
    main_urls = {
        str(episode.get("url", ""))
        for chapter in json.loads(MAIN_INDEX.read_text(encoding="utf-8")).get("chapters", [])
        for episode in chapter.get("episodes", [])
    } if MAIN_INDEX.exists() else set()
    series_rows: list[dict] = []
    retry: list[dict] = []
    accepted_urls = set(main_urls)
    skipped: list[str] = []
    for path in sorted(BATCH_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("series", [])
        if not rows:
            skipped.append(path.name)
        for series in rows:
            seen_numbers: set[object] = set()
            seen_urls: set[str] = set()
            errors: list[dict] = []
            for episode in series.get("episodes", []):
                error = episode_error(episode, seen_numbers, seen_urls, accepted_urls)
                seen_numbers.add(episode.get("number"))
                seen_urls.add(str(episode.get("url", "")))
                if error:
                    errors.append({"series": series.get("title", path.stem), "episode": episode.get("number"), "url": episode.get("url", ""), "reason": error})
            if not series.get("episodes"):
                errors.append({"series": series.get("title", path.stem), "episode": None, "url": "", "reason": "missing_episodes"})
            if errors:
                retry.extend(errors)
                continue
            series_rows.append(series)
            accepted_urls.update(seen_urls)

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    index = {
        "schemaVersion": 1,
        "source": {"provider": "GameKee", "catalogUrl": CATALOG_URL},
        "generatedAt": generated_at,
        "seriesCount": len(series_rows),
        "episodeCount": sum(len(row["episodes"]) for row in series_rows),
        "emptyBatchFiles": skipped,
        "series": series_rows,
    }
    SIDE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RETRY_QUEUE.write_text(json.dumps({"generatedAt": generated_at, "items": retry}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 番外剧情原文与总结（已采集系列）", "", "## 使用与剧透说明", "",
        "本文包含番外对话与页面总结，回答前须提示“含剧透”。页面总结保留为来源字段，未作为独立事实二次确认。", "",
        f"- 来源目录：{CATALOG_URL}", f"- 本次生成：{generated_at}",
        f"- 已覆盖系列：{len(series_rows)}", f"- 已覆盖话数：{index['episodeCount']}", "",
    ]
    for series in series_rows:
        lines.extend([f"## {series.get('title', '')}", ""])
        description = source_text(series.get("chapterSummary"))
        if description:
            lines.extend(["### 系列简介", "", description, ""])
        lines.extend(["### 剧情条目", ""])
        for episode in series["episodes"]:
            lines.extend([
                f"#### {episode.get('title', '')}", "", f"来源：{episode.get('url', '')}；内容类型：`dialogue`；可信度：`page_text`。", "",
                str(episode.get("dialogue", "")).strip(), "", "本话总结（来源字段，待与原文核验）：", "",
                source_text(episode.get("episodeSummary")) or "待补", "", "本章总结（来源字段，待与原文核验）：", "",
                source_text(episode.get("chapterSummaryInPlay")) or "待补", "",
            ])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    all_episodes = [episode for series in series_rows for episode in series.get("episodes", [])]
    dialogue_count = sum(bool(str(episode.get("dialogue", "")).strip()) for episode in all_episodes)
    episode_summary_count = sum(bool(source_text(episode.get("episodeSummary"))) for episode in all_episodes)
    chapter_summary_count = sum(bool(source_text(episode.get("chapterSummaryInPlay"))) for episode in all_episodes)

    manifest_path = BOT_ROOT / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = "astrbot_upload/" + OUTPUT.name
        files = [item for item in manifest.get("files", []) if item.get("path") != relative]
        files.append({"path": relative, "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(), "size": OUTPUT.stat().st_size})
        manifest["files"] = sorted(files, key=lambda item: item["path"])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    REPORT.write_text("\n".join([
        "# 番外剧情同步报告", "", f"- 生成时间：{generated_at}", f"- 来源：{CATALOG_URL}",
        f"- 已采集系列：{index['seriesCount']}", f"- 已采集对话条目：{index['episodeCount']}",
        f"- 对话完整：{dialogue_count}/{index['episodeCount']}",
        f"- 本话总结完整：{episode_summary_count}/{index['episodeCount']}",
        f"- 本章总结完整：{chapter_summary_count}/{index['episodeCount']}",
        f"- 空批次：{', '.join(skipped) or '无'}", f"- 重试项：{len(retry)}", f"- 结构化输出：{INDEX}", f"- AstrBot 输出：{OUTPUT}",
        "- 采集方式：浏览器逐话读取，逐话即时保存。",
    ]) + "\n", encoding="utf-8")
    print(json.dumps({"series": index["seriesCount"], "episodes": index["episodeCount"], "retry": len(retry), "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
