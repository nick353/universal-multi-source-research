#!/usr/bin/env python3
"""Render a deterministic source-coverage block for the top of a research brief."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SOURCE_LABELS = {
    "youtube": "YouTube",
    "x": "X",
    "reddit": "Reddit",
    "web": "通常Web",
    "github": "GitHub",
    "hacker_news": "Hacker News",
    "rss": "RSS",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "bluesky": "Bluesky",
    "linkedin": "LinkedIn",
    "arxiv": "arXiv",
    "polymarket": "Polymarket",
    "bilibili": "Bilibili",
    "xiaohongshu": "Xiaohongshu",
    "facebook": "Facebook",
    "v2ex": "V2EX",
    "xiaoyuzhou": "Xiaoyuzhou",
    "xueqiu": "Xueqiu",
}
ALLOWED_STATUSES = {"complete", "partial", "auth_required", "blocked", "no_results", "not_configured", "error", "planned"}


def load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("coverage input must be a JSON object")
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("coverage input must contain a sources array")
    return payload


def render(payload: dict) -> str:
    mode = payload.get("mode") or payload.get("mode_selection", {}).get("selected") or "standard"
    lines = [
        f"## 調査状況（自動選択モード: {mode}）",
        "",
        "| 媒体 | 状態 | 取得件数 | 取得方法・根拠 | 未取得理由 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for record in payload["sources"]:
        if not isinstance(record, dict):
            raise ValueError("each source record must be an object")
        source = str(record.get("source", "unknown"))
        status = str(record.get("status", "error"))
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"unsupported source status: {status}")
        # When relevance review has run, display only retained topic evidence;
        # raw search-hit counts must not inflate coverage.
        count = record.get("relevant_count", record.get("count", 0))
        if not isinstance(count, int) or count < 0:
            raise ValueError(f"count must be a non-negative integer for {source}")
        method = str(record.get("retrieval_method") or record.get("evidence_quality") or "—").replace("|", "\\|").replace("\n", " ")
        reason = str(record.get("reason") or "—").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {SOURCE_LABELS.get(source, source)} | `{status}` | {count} | {method} | {reason} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON source-status packet")
    parser.add_argument("--out", help="Markdown output path; stdout when omitted")
    args = parser.parse_args()
    markdown = render(load_payload(Path(args.input)))
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(markdown, encoding="utf-8")
        print(json.dumps({"out": str(output), "sources": markdown.count("\n| ")}, ensure_ascii=False))
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
