#!/usr/bin/env python3
"""Normalize adapter output into the skill's safe JSONL evidence ledger."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from source_contract import VALID_SOURCE_IDS, canonical_source, source_from_url


# Compatibility export for callers that used the old normalizer constant.
SOURCES = set(VALID_SOURCE_IDS)
EVIDENCE_STATUSES = {
    "complete",
    "partial",
    "auth_required",
    "blocked",
    "no_results",
    "not_configured",
    "error",
    "unverified",
}

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
    explicit = canonical_source(record.get("source", record.get("platform", "")))
    if explicit:
        return explicit
    url = str(record.get("url", record.get("link", "")))
    return source_from_url(url) or "web"


def as_text(record: dict[str, Any]) -> str:
    # Reddit search exposes the submission body as `selftext`; Reddit read and
    # X expose it as `text`. Keep both paths so a search result is not reduced
    # to a title-only citation.
    for key in ("text", "body", "selftext", "content", "description"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def source_url(record: dict[str, Any]) -> Any:
    return (
        record.get("url")
        or record.get("link")
        or record.get("permalink")
        or record.get("url_overridden_by_dest")
    )


def published_at(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return value


def topic_terms(topic: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}|[一-龯ぁ-んァ-ンー]{2,}", topic.lower())
    return list(dict.fromkeys(term for term in terms if term not in {"the", "and", "for", "with", "this", "that", "を", "の", "に", "で"}))


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


def normalize(record: dict[str, Any], topic: str | None = None) -> dict[str, Any]:
    method = str(record.get("retrieval_method", record.get("method", "unknown"))).strip() or "unknown"
    confidence = str(record.get("confidence", ""))
    if confidence not in {"high", "medium", "low"}:
        confidence = "high" if method in {"official_api", "praw", "manual"} else "medium" if method in {"agent_reach", "yt_dlp", "youtube_transcript_api", "rss"} else "low"
    claim_ids = record.get("claim_ids", record.get("claim_id", []))
    if isinstance(claim_ids, str):
        claim_ids = [claim_ids]
    if not isinstance(claim_ids, list):
        claim_ids = []
    normalized = {
        "source": infer_source(record),
        "url": source_url(record),
        "retrieved_at": record.get("retrieved_at") or now_iso(),
        "published_at": published_at(record.get("published_at", record.get("created_at", record.get("created_utc")))),
        "author": record.get("author", record.get("username")),
        "title": record.get("title", record.get("name")),
        "text": as_text(record),
        "quote": record.get("quote"),
        "engagement": engagement(record),
        "claim_ids": [str(item) for item in claim_ids if item is not None],
        "retrieval_method": method,
        "confidence": confidence,
        "status": record.get("status") if record.get("status") in EVIDENCE_STATUSES else "unverified",
    }
    if topic:
        terms = topic_terms(topic)
        haystack = " ".join(str(value or "") for value in (normalized.get("title"), normalized.get("text"))).lower()
        matched = [term for term in terms if term in haystack]
        normalized["topic"] = topic
        normalized["matched_topic_terms"] = matched
        normalized["topic_match_score"] = round(len(matched) / len(terms), 3) if terms else 0.0
    if record.get("topic_relevance") is not None:
        normalized["topic_relevance"] = record.get("topic_relevance")
    if record.get("relevance_reason") is not None:
        normalized["relevance_reason"] = record.get("relevance_reason")
    return normalized


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
    parser.add_argument("--topic", help="Topic used to add deterministic term-match metadata.")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w", encoding="utf-8") as handle:
        for record in load(args.input):
            handle.write(json.dumps(normalize(record, args.topic), ensure_ascii=False) + "\n")
            count += 1
    print(json.dumps({"records": count, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
