"""Merge saved GameKee event-story batches and build the AstrBot upload document."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLOT = ROOT / "data" / "plot"; EVENT = PLOT / "events"; BATCH = EVENT / "batches"
INDEX = EVENT / "event_story_index.json"; RETRY = EVENT / "retry_queue.json"
BOT = Path(r"F:\\Codex\\Nikke\\Nikke_Bot\\knowledge_base")
OUTPUT = BOT / "astrbot_upload" / "14_活动剧情_已采集章节.md"; REPORT = ROOT / "核心目录" / "报告" / "event_story_sync_report.md"
CATALOG = "https://www.gamekee.com/nikke/plot/catalog"

def text(value: object) -> str:
    return str(value.get("text", "")).strip() if isinstance(value, dict) else str(value or "").strip()

def main() -> None:
    main_index = json.loads((PLOT / "main_story_index.json").read_text(encoding="utf-8"))
    main_urls = {str(e.get("url", "")) for c in main_index.get("chapters", []) for e in c.get("episodes", [])}
    side_path = PLOT / "side_stories" / "side_story_index.json"
    side = json.loads(side_path.read_text(encoding="utf-8")) if side_path.exists() else {}
    known_urls = main_urls | {str(e.get("url", "")) for s in side.get("series", []) for e in s.get("episodes", [])}
    series_rows=[]; retry=[]; accepted=set(known_urls); skipped=[]
    for path in sorted(BATCH.glob("*.json")):
        payload=json.loads(path.read_text(encoding="utf-8")); rows=payload.get("series", [])
        if not rows: skipped.append(path.name)
        for series in rows:
            seen_n=set(); seen_u=set(); errors=[]
            for e in series.get("episodes", []):
                url=str(e.get("url", "")); reason=""
                if not e.get("title"): reason="missing_title"
                elif not url.startswith("https://www.gamekee.com/nikke/plot/play/"): reason="invalid_source_url"
                elif not str(e.get("dialogue", "")).strip(): reason="missing_dialogue"
                elif e.get("number") in seen_n: reason="duplicate_episode_number"
                elif url in seen_u or url in accepted: reason="duplicate_source_url"
                seen_n.add(e.get("number")); seen_u.add(url)
                if reason: errors.append({"series":series.get("title",path.stem),"episode":e.get("number"),"url":url,"reason":reason})
            if not series.get("episodes"): errors.append({"series":series.get("title",path.stem),"episode":None,"url":"","reason":"missing_episodes"})
            if errors: retry.extend(errors); continue
            series_rows.append(series); accepted.update(seen_u)
    now=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    idx={"schemaVersion":1,"source":{"provider":"GameKee","catalogUrl":CATALOG},"generatedAt":now,"seriesCount":len(series_rows),"episodeCount":sum(len(s.get("episodes",[])) for s in series_rows),"emptyBatchFiles":skipped,"series":series_rows}
    EVENT.mkdir(parents=True,exist_ok=True); INDEX.write_text(json.dumps(idx,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); RETRY.write_text(json.dumps({"generatedAt":now,"items":retry},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# 活动剧情原文与总结（已采集系列）","","## 使用与剧透说明","","本文包含活动剧情对话与页面总结，回答前须提示“含剧透”。页面总结保留为来源字段，未作为独立事实二次确认。","",f"- 来源目录：{CATALOG}",f"- 本次生成：{now}",f"- 已覆盖系列：{idx['seriesCount']}",f"- 已覆盖话数：{idx['episodeCount']}",""]
    for s in series_rows:
        lines += [f"## {s.get('title','')}",""]; desc=text(s.get("chapterSummary"))
        if desc: lines += ["### 活动简介","",desc,""]
        lines += ["### 剧情条目",""]
        for e in s.get("episodes",[]): lines += [f"#### {e.get('title','')}","",f"来源：{e.get('url','')}；内容类型：`dialogue`；可信度：`page_text`。","",str(e.get('dialogue','')).strip(),"","本话总结（来源字段，待与原文核验）：","",text(e.get('episodeSummary')) or "待补","","本章总结（来源字段，待与原文核验）：","",text(e.get('chapterSummaryInPlay')) or "待补",""]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text("\n".join(lines),encoding="utf-8")
    manifest=BOT/"MANIFEST.json"
    if manifest.exists():
        m=json.loads(manifest.read_text(encoding="utf-8")); rel="astrbot_upload/"+OUTPUT.name; files=[x for x in m.get("files",[]) if x.get("path")!=rel]; files.append({"path":rel,"sha256":hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),"size":OUTPUT.stat().st_size}); m["files"]=sorted(files,key=lambda x:x["path"]); manifest.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    eps=[e for s in series_rows for e in s.get("episodes",[])]; report=["# 活动剧情同步报告","",f"- 生成时间：{now}",f"- 来源：{CATALOG}",f"- 已采集系列：{idx['seriesCount']}",f"- 已采集话数：{idx['episodeCount']}",f"- 对话完整：{sum(bool(text(e.get('dialogue'))) for e in eps)}/{idx['episodeCount']}",f"- 本话总结完整：{sum(bool(text(e.get('episodeSummary'))) for e in eps)}/{idx['episodeCount']}",f"- 本章总结完整：{sum(bool(text(e.get('chapterSummaryInPlay'))) for e in eps)}/{idx['episodeCount']}",f"- 重试项：{len(retry)}",f"- 结构化输出：{INDEX}",f"- AstrBot 输出：{OUTPUT}","- 采集方式：浏览器逐话读取，逐话即时保存。"]
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text("\n".join(report)+"\n",encoding="utf-8"); print(json.dumps({"series":idx['seriesCount'],"episodes":idx['episodeCount'],"retry":len(retry),"output":str(OUTPUT)},ensure_ascii=False))

if __name__ == "__main__": main()
