#!/usr/bin/env python3
"""Run a bounded, read-only live smoke search for configured community sources.

This is an acquisition check, not a substitute for collecting and opening the
returned records.  It intentionally stores only safe metadata and source URLs;
post bodies, credentials, and upstream stderr are never persisted.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_COMMANDS = {
    "x": ("twitter", "search"),
    "reddit": ("reddit", "search"),
}
ALLOWED_SOURCES = set(SOURCE_COMMANDS)
MAX_URLS = 40


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _executable(value: str) -> str:
    if Path(value).is_absolute():
        return value
    return shutil.which(value) or value


def _items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "results", "posts", "data", "tweets", "submissions"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return candidate
        if any(key in payload for key in ("id", "url", "permalink")):
            return [payload]
    return []


def _urls(items: list[Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        candidates = [item.get("url"), item.get("permalink")]
        quoted = item.get("quoted_tweet")
        if isinstance(quoted, dict):
            candidates.append(quoted.get("url"))
        for value in candidates:
            if not isinstance(value, str) or not value.startswith(("https://", "http://")):
                continue
            if value not in seen:
                seen.add(value)
                values.append(value)
            if len(values) >= MAX_URLS:
                return values
    return values


def _content(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("text", "body", "selftext", "content", "description", "snippet"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _topic_terms(query: str) -> list[str]:
    values = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}|[一-龯ぁ-んァ-ンー]{2,}", query.lower())
    return list(dict.fromkeys(value for value in values if value not in {"the", "and", "for", "with", "を", "の", "に", "で"}))


def _content_stats(items: list[Any], query: str) -> tuple[int, int, list[str], int]:
    terms = _topic_terms(query)
    minimum_matches = max(1, min(2, len(terms)))
    content_count = 0
    matching_count = 0
    for item in items:
        body = _content(item)
        if not body:
            continue
        content_count += 1
        title = item.get("title", "") if isinstance(item, dict) else ""
        haystack = f"{title} {body}".lower()
        if sum(term in haystack for term in terms) >= minimum_matches:
            matching_count += 1
    return content_count, matching_count, terms, minimum_matches


def _failure_status(returncode: int, stderr: str) -> tuple[str, str]:
    text = stderr.lower()
    if any(token in text for token in ("login", "log in", "authenticate", "unauthorized", "401", "cookie", "credential")):
        return "auth_required", "The read-only source search requires authentication."
    if any(token in text for token in ("forbidden", "403", "blocked", "captcha", "rate limit", "too many requests")):
        return "blocked", "The source rejected or rate-limited the read-only search."
    if returncode == 124:
        return "error", "The read-only source search timed out."
    return "error", "The read-only source search exited unsuccessfully."


def probe_source(source: str, query: str, executable: str, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    # OpenCLI adapter commands normally use an ephemeral site tab. Explicitly
    # reuse the site's persistent background session so X/Reddit research does
    # not create a new visible Chrome window for every read-only command.
    # Persistent sessions intentionally keep and reuse their browser
    # container; do not request ephemeral tab cleanup here.
    command = [
        executable,
        *SOURCE_COMMANDS[source],
        query,
        "-f", "json",
        "--window", "background",
        "--site-session", "persistent",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "source": source,
            "status": "error",
            "count": 0,
            "evidence_urls": [],
            "retrieval_method": "OpenCLI read-only search",
            "backend": "OpenCLI",
            "reason": "The read-only source search timed out.",
            "error_code": "timeout",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except OSError:
        return {
            "source": source,
            "status": "not_configured",
            "count": 0,
            "evidence_urls": [],
            "retrieval_method": "OpenCLI read-only search",
            "backend": "OpenCLI",
            "reason": "OpenCLI could not be started.",
            "error_code": "executable_unavailable",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    if result.returncode != 0:
        status, reason = _failure_status(result.returncode, result.stderr)
        return {
            "source": source,
            "status": status,
            "count": 0,
            "evidence_urls": [],
            "retrieval_method": "OpenCLI read-only search",
            "backend": "OpenCLI",
            "reason": reason,
            "error_code": f"exit_{result.returncode}",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "source": source,
            "status": "error",
            "count": 0,
            "evidence_urls": [],
            "retrieval_method": "OpenCLI read-only search",
            "backend": "OpenCLI",
            "reason": "OpenCLI returned a non-JSON search result.",
            "error_code": "invalid_json",
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    records = _items(payload)
    urls = _urls(records)
    content_count, matching_count, query_terms, minimum_matches = _content_stats(records, query)
    if not records:
        status = "no_results"
        reason = "The read-only source search returned no records."
    elif not urls:
        status = "partial"
        reason = "The source returned records but no stable source URLs were exposed."
    elif not content_count:
        status = "partial"
        reason = "The source returned URLs but no readable source body was exposed."
    else:
        status = "complete"
        reason = "The read-only source search returned source-native records and URLs."
    return {
        "source": source,
        "status": status,
        "count": len(records),
        "content_records": content_count,
        "topic_match_candidates": matching_count,
        "topic_terms": query_terms,
        "topic_match_min_terms": minimum_matches,
        "evidence_urls": urls,
        "retrieval_method": "OpenCLI read-only search",
        "backend": "OpenCLI",
        "reason": reason,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, choices=sorted(ALLOWED_SOURCES))
    parser.add_argument("--query", required=True)
    parser.add_argument("--command", default="opencli", help="OpenCLI executable name or absolute path.")
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--out", required=True, help="JSON output packet path.")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    packet = {
        "version": 1,
        "retrieved_at": _now(),
        "query": args.query,
        "backend": "OpenCLI",
        "read_only": True,
        "browser_policy": {
            "window": "background",
            "site_session": "persistent",
            "keep_tab": True,
        },
        "sources": [
            probe_source(source, args.query, _executable(args.command), args.timeout)
            for source in dict.fromkeys(args.source)
        ],
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(output), "sources": len(packet["sources"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
