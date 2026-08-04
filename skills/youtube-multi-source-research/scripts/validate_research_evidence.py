#!/usr/bin/env python3
"""Fail closed when a research packet claims retrieval without evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate(payload: dict[str, Any], required_sources: list[str]) -> dict[str, Any]:
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
        if status == "planned":
            blockers.append({"code": "planned_not_retrieved", "message": f"{source} is only planned, not retrieved."})

    for source in dict.fromkeys(required_sources):
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

    return {
        "valid": not blockers,
        "research_incomplete": bool(blockers),
        "checked_at": _now(),
        "required_sources": list(dict.fromkeys(required_sources)),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Source-status or live-probe JSON packet.")
    parser.add_argument("--require-source", action="append", default=[], help="Source that must have retrieved URL evidence.")
    parser.add_argument("--out", help="Optional validation JSON path.")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("input must be a JSON object")
    result = validate(payload, args.require_source)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
