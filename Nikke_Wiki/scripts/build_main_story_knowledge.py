"""Merge saved GameKee main-story batches and build one AstrBot upload document."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = ROOT / "data" / "plot" / "batches"
PLOT_DIR = ROOT / "data" / "plot"
INDEX = PLOT_DIR / "main_story_index.json"
RETRY_QUEUE = PLOT_DIR / "retry_queue.json"
BOT_ROOT = Path(r"F:\Codex\Nikke\Nikke_Bot\knowledge_base")
UPLOAD = BOT_ROOT / "astrbot_upload"
OUTPUT = UPLOAD / "12_主线剧情_已采集章节.md"
REPORT = ROOT / "核心目录" / "报告" / "plot_sync_report.md"
CATALOG_URL = "https://www.gamekee.com/nikke/plot/catalog"


def chapter_number(chapter: dict) -> int:
    value = str(chapter.get("number", ""))
    if not value:
        match = re.search(r"第(\d+)章", str(chapter.get("title", "")))
        value = match.group(1) if match else ""
    value = value.lstrip("0")
    return int(value or 0)


def source_text(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("text", "")).strip()
    return str(value or "").strip()


def episode_error(episode: dict) -> str:
    if not episode.get("title"):
        return "missing_title"
    if not str(episode.get("url", "")).startswith("https://www.gamekee.com/nikke/plot/play/"):
        return "invalid_source_url"
    dialogue = str(episode.get("dialogue", "")).strip()
    if not dialogue:
        return "missing_dialogue"
    if "\ufffd" in dialogue:
        return "encoding_replacement_character"
    return ""


def main() -> None:
    chapters: dict[int, dict] = {}
    skipped: list[str] = []
    retry_queue: list[dict] = []
    accepted_episode_urls: set[str] = set()
    for path in sorted(BATCH_DIR.glob("*.json")):
        if path.name.endswith(".partial.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("chapters", [])
        if not rows:
            skipped.append(path.name)
        for chapter in rows:
            number = chapter_number(chapter)
            episodes = chapter.get("episodes", [])
            errors = []
            seen_numbers = set()
            seen_urls = set()
            for episode in episodes:
                error = episode_error(episode)
                if episode.get("number") in seen_numbers:
                    error = error or "duplicate_episode_number"
                if episode.get("url") in seen_urls:
                    error = error or "duplicate_episode_url"
                if episode.get("url") in accepted_episode_urls:
                    error = error or "duplicate_source_url_in_another_chapter"
                seen_numbers.add(episode.get("number"))
                seen_urls.add(episode.get("url"))
                if error:
                    errors.append({"episode": episode.get("number"), "url": episode.get("url", ""), "reason": error})
            if not episodes:
                errors.append({"episode": None, "url": "", "reason": "missing_episodes"})
            if errors:
                retry_queue.extend({"chapter": number, **error} for error in errors)
                continue
            chapters[number] = chapter
            accepted_episode_urls.update(str(episode.get("url", "")) for episode in episodes)

    ordered = [chapters[key] for key in sorted(chapters)]
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    index = {
        "schemaVersion": 1,
        "source": {"provider": "GameKee", "catalogUrl": CATALOG_URL},
        "generatedAt": fetched_at,
        "availableChapterNumbers": [chapter_number(chapter) for chapter in ordered],
        "chapterCount": len(ordered),
        "episodeCount": sum(len(chapter.get("episodes", [])) for chapter in ordered),
        "emptyBatchFiles": skipped,
        "chapters": ordered,
    }
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RETRY_QUEUE.write_text(json.dumps({"generatedAt": fetched_at, "items": retry_queue}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# 主线剧情原文与总结（已采集章节）",
        "",
        "## 使用与剧透说明",
        "",
        "本文包含主线对话与页面总结，回答前须提示“含剧透”。对话、单话总结和章节简介均保留 GameKee 页面来源；总结若与对话不一致，只能标记为来源待核验，不能据此扩写为剧情事实。",
        "",
        f"- 来源目录：{CATALOG_URL}",
        f"- 本次生成：{fetched_at}",
        f"- 已覆盖章节：" + "、".join(str(chapter_number(chapter)).zfill(2) for chapter in ordered),
        f"- 已覆盖话数：{index['episodeCount']}",
        "- 核验状态：页面级原文已采集；章节总结和本话总结为来源字段，未作为独立事实二次确认。",
        "",
    ]
    for chapter in ordered:
        lines.extend([f"## {chapter.get('title', '')}", ""])
        summary = str(chapter.get("chapterSummary", "")).strip()
        if summary:
            lines.extend(["### 页面章节简介", "", summary, ""])
        lines.extend(["### 剧情条目", ""])
        for episode in chapter.get("episodes", []):
            lines.extend([
                f"#### {episode.get('title', '')}",
                "",
                f"来源：{episode.get('url', '')}；内容类型：`dialogue`；可信度：`page_text`。",
                "",
                episode.get("dialogue", "").strip(),
                "",
                "本话总结（来源字段，待与原文核验）：",
                "",
                source_text(episode.get("episodeSummary")) or "待补",
                "",
            ])
        lines.append("")
    UPLOAD.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    # The base builder creates MANIFEST before this optional plot document.
    # Add its digest so the standard AstrBot validator remains authoritative.
    manifest_path = BOT_ROOT / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        relative = "astrbot_upload/" + OUTPUT.name
        digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
        files = [item for item in manifest.get("files", []) if item.get("path") != relative]
        files.append({"path": relative, "sha256": digest, "size": OUTPUT.stat().st_size})
        manifest["files"] = sorted(files, key=lambda item: item["path"])
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = [
        "# 主线剧情同步报告",
        "",
        f"- 生成时间：{fetched_at}",
        f"- 来源：{CATALOG_URL}",
        f"- 已采集章节：{index['chapterCount']}（" + ", ".join(str(chapter_number(chapter)).zfill(2) for chapter in ordered) + "）",
        f"- 已采集对话条目：{index['episodeCount']}",
        "- 本话总结：与对话条目一并保存，来自页面“总结”页签。",
        "- 本章总结：当前目录页面提供“页面章节简介”；播放器的“本章总结”字段存在与对话不一致的迹象，未写入事实分析。",
        f"- 空批次（等待重试）：{', '.join(skipped) or '无'}",
        f"- 不完整话数重试项：{len(retry_queue)}",
        f"- 结构化输出：{INDEX}",
        f"- AstrBot 输出：{OUTPUT}",
        "- 结论边界：当前仅对已采集章节建立原文检索；未采集章节不能回答为已核验剧情。",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"chapters": index["chapterCount"], "episodes": index["episodeCount"], "retry": len(retry_queue), "output": str(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
