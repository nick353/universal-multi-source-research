#!/usr/bin/env python3
"""Check that retained evidence contains readable, topic-relevant source content."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


RELEVANCE_VALUES = {"relevant", "partial", "irrelevant"}
STOPWORDS = {"the", "and", "for", "with", "this", "that", "from", "into", "about", "を", "の", "に", "で", "が", "は", "と"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def iter_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        yield from (item for item in value if isinstance(item, dict))
        return
    if isinstance(value, dict):
        for key in ("evidence", "results", "items", "data"):
            if isinstance(value.get(key), (list, dict)):
                yield from iter_records(value[key])
                return
        yield value


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.extend(iter_records(json.loads(line)))
        return records
    return list(iter_records(json.loads(path.read_text(encoding="utf-8"))))


def terms(topic: str, keywords: list[str]) -> list[str]:
    values = keywords or re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}|[一-龯ぁ-んァ-ンー]{2,}", topic.lower())
    return list(dict.fromkeys(value.lower() for value in values if value and value.lower() not in STOPWORDS))


def matches(record: dict[str, Any], query_terms: list[str]) -> list[str]:
    haystack = " ".join(str(value or "") for value in (record.get("title"), record.get("text"))).lower()
    return [term for term in query_terms if term in haystack]


def validate(records: list[dict[str, Any]], topic: str, required_sources: list[str], keywords: list[str], minimum: int) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    query_terms = terms(topic, keywords)
    counts = {source: 0 for source in dict.fromkeys(required_sources)}
    reviewed = {source: 0 for source in dict.fromkeys(required_sources)}
    for index, record in enumerate(records):
        source = str(record.get("source", ""))
        url = record.get("url")
        text = str(record.get("text") or "").strip()
        relevance = record.get("topic_relevance")
        matched = matches(record, query_terms)
        if not source or not isinstance(url, str) or not url.startswith(("http://", "https://")):
            blockers.append({"code": "missing_direct_source", "message": f"Evidence record {index} has no direct source URL."})
        if not text:
            blockers.append({"code": "missing_source_content", "message": f"Evidence record {index} has no source body/text."})
        if relevance not in RELEVANCE_VALUES:
            blockers.append({"code": "relevance_unreviewed", "message": f"Evidence record {index} is missing topic_relevance."})
        else:
            if source in reviewed:
                reviewed[source] += 1
            if relevance == "relevant" and text and isinstance(url, str):
                if source in counts:
                    counts[source] += 1
                if not matched:
                    blockers.append({"code": "relevant_without_topic_match", "message": f"Evidence record {index} is marked relevant but has no matching topic term."})
        if relevance == "irrelevant":
            # Irrelevant candidates may remain in an audit ledger, but cannot
            # contribute to the coverage count or final claim set.
            continue

    for source in dict.fromkeys(required_sources):
        if reviewed[source] == 0:
            blockers.append({"code": "source_content_not_reviewed", "message": f"Required source {source} has no reviewed content records."})
        if counts[source] < minimum:
            blockers.append({"code": "insufficient_relevant_evidence", "message": f"Required source {source} has {counts[source]} relevant records; minimum is {minimum}."})

    return {
        "valid": not blockers,
        "research_incomplete": bool(blockers),
        "checked_at": now_iso(),
        "topic": topic,
        "topic_terms": query_terms,
        "required_sources": list(dict.fromkeys(required_sources)),
        "minimum_relevant_per_source": minimum,
        "relevant_counts": counts,
        "reviewed_counts": reviewed,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Normalized evidence JSONL or JSON packet.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--keyword", action="append", default=[], help="Important entity/issue term; repeat for concise source-specific terms.")
    parser.add_argument("--require-source", action="append", default=[])
    parser.add_argument("--min-relevant", type=int, default=2)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.min_relevant <= 0:
        parser.error("--min-relevant must be positive")
    result = validate(load_records(Path(args.input)), args.topic, args.require_source, args.keyword, args.min_relevant)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
