#!/usr/bin/env python3
"""Fail closed when a research packet claims retrieval without evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ALLOWED_STATUSES = {
    "complete",
    "partial",
    "auth_required",
    "blocked",
    "no_results",
    "not_configured",
    "error",
    "planned",
}

# The fixed completion contract for an ordinary, non-narrowed research run.
# Keep this order stable: it is also the order used in blocker reports.
CORE_REQUIRED_SOURCES = ("youtube", "x", "reddit", "web")
CORE_COMPLETION_CONTRACT = "core4_strict_v1"
NATIVE_HOSTS = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"},
    "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
    "reddit": {"reddit.com", "www.reddit.com", "old.reddit.com", "redd.it"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _youtube_usable_count(record: dict[str, Any]) -> int | None:
    """Return an explicit usable-video count; never infer it from candidates."""
    value = record.get("usable_count")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _valid_http_urls(record: dict[str, Any]) -> list[str]:
    urls = record.get("evidence_urls", [])
    if not isinstance(urls, list):
        return []
    return [
        url.strip()
        for url in urls
        if isinstance(url, str)
        and url.strip()
        and urlparse(url.strip()).scheme in {"http", "https"}
        and bool(urlparse(url.strip()).netloc)
    ]


def _has_native_url(source: str, urls: list[str]) -> bool:
    if source == "web":
        return bool(urls)
    hosts = NATIVE_HOSTS.get(source, set())
    for url in urls:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
        if host in hosts or any(host.endswith(f".{suffix}") for suffix in hosts):
            return True
    return False


def _body_evidence_count(record: dict[str, Any]) -> int:
    """Return an explicit body-bearing evidence count; never infer from URLs."""
    for key in ("body_evidence_count", "content_records"):
        value = record.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > 0:
            return value
    return 0


def _strict_blocker(source: str, stage: str, reason: str, message: str) -> dict[str, str]:
    return {
        "code": "required_source_unsatisfied",
        "source": source,
        "stage": stage,
        "reason": reason,
        "message": message,
    }


def _validate_core_source(record: dict[str, Any] | None, source: str) -> list[dict[str, str]]:
    """Validate one source against the non-narrowed four-media contract."""
    if record is None:
        return [_strict_blocker(
            source,
            "aggregate",
            "missing_status_record",
            f"Required source {source} has no terminal status record.",
        )]

    blockers: list[dict[str, str]] = []
    status = str(record.get("status", ""))
    if status != "complete":
        reason = {
            "auth_required": "auth_required",
            "not_configured": "unavailable",
            "no_results": "no_valid_evidence",
            "planned": "not_executed",
            "partial": "terminal_failure",
        }.get(status, "execution_error")
        blockers.append(_strict_blocker(
            source,
            "validate",
            reason,
            f"Required source {source} is {status or 'unknown'}; complete requires terminal success.",
        ))

    if record.get("runner_executed") is not True:
        blockers.append(_strict_blocker(
            source,
            "retrieve",
            "runner_not_executed",
            f"Required source {source} has no dedicated runner execution proof.",
        ))
    if record.get("terminal_success") is not True:
        blockers.append(_strict_blocker(
            source,
            "retrieve",
            "terminal_failure",
            f"Required source {source} has no terminal-success proof.",
        ))

    urls = _valid_http_urls(record)
    if record.get("evidence_retrieved") is not True or not urls:
        blockers.append(_strict_blocker(
            source,
            "validate",
            "no_valid_evidence",
            f"Required source {source} has no valid retrieved evidence URL set.",
        ))
    elif not _has_native_url(source, urls):
        blockers.append(_strict_blocker(
            source,
            "validate",
            "invalid_provenance",
            f"Required source {source} has no source-native evidence URL.",
        ))

    retrieval_method = record.get("retrieval_method")
    if not isinstance(retrieval_method, str) or not retrieval_method.strip():
        blockers.append(_strict_blocker(
            source,
            "validate",
            "invalid_provenance",
            f"Required source {source} has no retrieval method/provenance.",
        ))

    if source == "youtube":
        usable_count = _youtube_usable_count(record)
        if usable_count is None or usable_count <= 0:
            blockers.append(_strict_blocker(
                source,
                "validate",
                "no_valid_evidence",
                "YouTube requires a positive usable transcript/metadata evidence count.",
            ))
    elif _body_evidence_count(record) <= 0:
        blockers.append(_strict_blocker(
            source,
            "validate",
            "no_valid_evidence",
            f"Required source {source} has no explicit body-bearing evidence count.",
        ))
    return blockers


def validate(
    payload: dict[str, Any],
    required_sources: list[str],
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    records = payload.get("sources")
    if not isinstance(records, list):
        return {"valid": False, "research_incomplete": True, "blockers": [{"code": "missing_sources", "message": "The packet has no sources array."}]}

    by_source: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            blockers.append({"code": "invalid_source_record", "message": "A source record is not an object."})
            continue
        source = str(record.get("source", ""))
        status = str(record.get("status", ""))
        if not source:
            blockers.append({"code": "missing_source", "message": "A source record has no source ID."})
            continue
        by_source[source] = record
        if status not in ALLOWED_STATUSES:
            blockers.append({"code": "invalid_status", "message": f"{source} has unsupported status {status!r}."})
            continue
        count = record.get("count", 0)
        if not isinstance(count, int) or count < 0:
            blockers.append({"code": "invalid_count", "message": f"{source} count must be a non-negative integer."})
        urls = record.get("evidence_urls", [])
        if urls is not None and not isinstance(urls, list):
            blockers.append({"code": "invalid_evidence_urls", "message": f"{source} evidence_urls must be an array."})
        if status == "complete" and (not isinstance(count, int) or count <= 0 or not urls):
            blockers.append({"code": "complete_without_evidence", "message": f"{source} is complete without a positive count and source URL evidence."})
        if source == "youtube":
            usable_count = _youtube_usable_count(record)
            if usable_count is None:
                blockers.append({"code": "youtube_usable_count_missing", "message": "YouTube must declare usable_count; candidate videos are not transcript evidence."})
            elif status == "complete" and usable_count <= 0:
                blockers.append({"code": "youtube_complete_without_usable_evidence", "message": "YouTube cannot be complete when usable_count is zero."})
        if status == "planned":
            blockers.append({"code": "planned_not_retrieved", "message": f"{source} is only planned, not retrieved."})

    normalized_required_sources = list(dict.fromkeys(required_sources))
    for source in normalized_required_sources:
        record = by_source.get(source)
        if record is None:
            blockers.append({"code": "required_source_missing", "message": f"Required source {source} has no status record."})
            continue
        status = str(record.get("status", ""))
        urls = record.get("evidence_urls", [])
        if status not in {"complete", "partial"}:
            blockers.append({"code": "required_source_not_retrieved", "message": f"Required source {source} is {status or 'unknown'}, so this run is incomplete."})
        elif not urls:
            blockers.append({"code": "required_source_without_urls", "message": f"Required source {source} has no source-native evidence URLs."})
        if source == "youtube":
            usable_count = _youtube_usable_count(record)
            if usable_count is None:
                blockers.append({"code": "youtube_usable_count_missing", "message": "Required YouTube source has no explicit usable transcript/metadata evidence count."})
            elif usable_count <= 0:
                blockers.append({"code": "youtube_usable_evidence_missing", "message": "Required YouTube source has candidate URLs but no usable transcript/metadata evidence."})

    if require_complete:
        # This is deliberately separate from the backwards-compatible
        # --require-source behavior above. Partial source records are useful for
        # diagnostics, but they must never become a completed four-media brief.
        for source in CORE_REQUIRED_SOURCES:
            blockers.extend(_validate_core_source(by_source.get(source), source))

    result = {
        "valid": not blockers,
        "research_incomplete": bool(blockers),
        "checked_at": _now(),
        "required_sources": list(CORE_REQUIRED_SOURCES) if require_complete else normalized_required_sources,
        "blockers": blockers,
    }
    if require_complete:
        result["completion_contract"] = CORE_COMPLETION_CONTRACT
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source-status or live-probe JSON packet.")
    parser.add_argument("--require-source", action="append", default=[], help="Source that must have retrieved URL evidence.")
    parser.add_argument(
        "--require-core-4",
        action="store_true",
        help="Require complete terminal evidence for YouTube, X, Reddit, and Web in fixed order.",
    )
    parser.add_argument("--out", help="Optional validation JSON path.")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("input must be a JSON object")
    result = validate(
        payload,
        list(CORE_REQUIRED_SOURCES) if args.require_core_4 else args.require_source,
        require_complete=args.require_core_4,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
