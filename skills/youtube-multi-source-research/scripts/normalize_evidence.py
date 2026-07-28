#!/usr/bin/env python3
"""Normalize adapter output into the skill's safe JSONL evidence ledger."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Iterable


SOURCES = {"youtube", "x", "reddit", "web", "github", "hacker_news", "tiktok", "other"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(value, dict):
        for key in ("evidence", "results", "items", "data"):
            if key in value and isinstance(value[key], (list, dict)):
                yield from iter_records(value[key])
                return
        yield value


def infer_source(record: dict[str, Any]) -> str:
    value = str(record.get("source", record.get("platform", ""))).lower().strip()
    aliases = {"twitter": "x", "reddit.com": "reddit", "youtube.com": "youtube", "github.com": "github", "hn": "hacker_news"}
    value = aliases.get(value, value)
    if value in SOURCES:
        return value
    url = str(record.get("url", record.get("link", "")))
    host = urlparse(url).netloc.lower()
    if "youtube" in host or "youtu.be" in host:
        return "youtube"
    if "reddit" in host:
        return "reddit"
    if host in {"x.com", "twitter.com", "t.co"} or "twitter" in host:
        return "x"
    if "github" in host:
        return "github"
    return "web"


def as_text(record: dict[str, Any]) -> str:
    for key in ("text", "body", "content", "description", "snippet", "summary"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def engagement(record: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    source_value = record.get("engagement")
    if isinstance(source_value, dict):
        values.update({key: source_value.get(key) for key in ("score", "comments", "likes", "views", "reposts") if key in source_value})
    aliases = {"score": ("score", "upvotes", "points"), "comments": ("comments", "comment_count"), "likes": ("likes", "like_count"), "views": ("views", "view_count"), "reposts": ("reposts", "retweets", "shares")}
    for target, keys in aliases.items():
        if target in values:
            continue
        for key in keys:
            if key in record:
                values[target] = record[key]
                break
    return values


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    method = str(record.get("retrieval_method", record.get("method", "manual")))
    confidence = str(record.get("confidence", ""))
    if confidence not in {"high", "medium", "low"}:
        confidence = "high" if method in {"official_api", "praw", "manual"} else "medium" if method in {"agent_reach", "yt_dlp", "youtube_transcript_api", "rss"} else "low"
    claim_ids = record.get("claim_ids", record.get("claim_id", []))
    if isinstance(claim_ids, str):
        claim_ids = [claim_ids]
    if not isinstance(claim_ids, list):
        claim_ids = []
    return {
        "source": infer_source(record),
        "url": record.get("url", record.get("link")),
        "retrieved_at": record.get("retrieved_at") or now_iso(),
        "published_at": record.get("published_at", record.get("created_at")),
        "author": record.get("author", record.get("username")),
        "title": record.get("title", record.get("name")),
        "text": as_text(record),
        "quote": record.get("quote"),
        "engagement": engagement(record),
        "claim_ids": [str(item) for item in claim_ids if item is not None],
        "retrieval_method": method,
        "confidence": confidence,
        "status": record.get("status", "complete"),
    }


def load(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield from iter_records(json.loads(line))
    else:
        yield from iter_records(json.loads(path.read_text(encoding="utf-8")))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", encoding="utf-8") as handle:
        for record in load(args.input):
            handle.write(json.dumps(normalize(record), ensure_ascii=False) + "\n")
            count += 1
    print(json.dumps({"records": count, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
