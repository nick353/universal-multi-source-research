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
RESEARCH_MODES = ("quick", "standard", "deep")
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


def _mode_evidence_count(record: dict[str, Any], source: str) -> int:
    """Return the count that is eligible for a selected-mode evidence floor."""
    if source == "youtube":
        value = _youtube_usable_count(record)
        return value if value is not None else 0
    body_count = _body_evidence_count(record)
    if body_count > 0:
        return body_count
    value = record.get("count")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _mode_minimums(plan: dict[str, Any]) -> dict[str, int]:
    limits = plan.get("collection_limits")
    limits = limits if isinstance(limits, dict) else {}
    youtube_policy = plan.get("youtube_policy")
    youtube_policy = youtube_policy if isinstance(youtube_policy, dict) else {}
    minimums: dict[str, int] = {}
    youtube_minimum = youtube_policy.get("minimum_distinct_count")
    if not isinstance(youtube_minimum, int) or isinstance(youtube_minimum, bool):
        youtube_limit = limits.get("youtube", {})
        youtube_items = youtube_limit.get("items", {}) if isinstance(youtube_limit, dict) else {}
        youtube_minimum = youtube_items.get("min") if isinstance(youtube_items, dict) else None
    if isinstance(youtube_minimum, int) and not isinstance(youtube_minimum, bool) and youtube_minimum >= 0:
        minimums["youtube"] = youtube_minimum
    for source, dimension in (("x", "primary_posts"), ("reddit", "submissions"), ("web", "opened_pages")):
        source_limits = limits.get(source, {})
        source_limit = source_limits.get(dimension, {}) if isinstance(source_limits, dict) else {}
        minimum = source_limit.get("min") if isinstance(source_limit, dict) else None
        if isinstance(minimum, int) and not isinstance(minimum, bool) and minimum >= 0:
            minimums[source] = minimum
    return minimums


def _validate_mode_contract(
    payload: dict[str, Any],
    by_source: dict[str, dict[str, Any]],
    plan: dict[str, Any] | None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Validate that the status packet actually ran the selected workload."""
    blockers: list[dict[str, str]] = []
    contract: dict[str, Any] = {
        "valid": True,
        "mode": None,
        "minimums": {},
        "query_families_required": [],
        "query_families_executed": [],
    }
    if not isinstance(plan, dict):
        blocker = {"code": "mode_contract_missing_plan", "message": "Mode validation requires the exact research-plan.json used for this run."}
        return [blocker], {**contract, "valid": False}

    expected_mode = plan.get("mode")
    actual_mode = payload.get("research_mode")
    contract["mode"] = expected_mode
    if expected_mode not in RESEARCH_MODES:
        blockers.append({"code": "invalid_plan_mode", "message": f"Research plan has unsupported mode {expected_mode!r}."})
    if actual_mode != expected_mode:
        blockers.append({
            "code": "research_mode_mismatch",
            "message": f"Source status research_mode {actual_mode!r} does not match plan mode {expected_mode!r}.",
        })
    packet_mode = payload.get("mode")
    if packet_mode is not None and packet_mode != expected_mode:
        blockers.append({
            "code": "mode_field_mismatch",
            "message": f"Source status mode {packet_mode!r} does not match plan mode {expected_mode!r}.",
        })
    plan_run_id = plan.get("run_id")
    packet_run_id = payload.get("run_id")
    if plan_run_id and packet_run_id != plan_run_id:
        blockers.append({
            "code": "run_id_mismatch",
            "message": f"Source status run_id {packet_run_id!r} does not match plan run_id {plan_run_id!r}.",
        })

    required = plan.get("required_sources")
    if required != list(CORE_REQUIRED_SOURCES):
        blockers.append({
            "code": "required_source_contract_mismatch",
            "message": "The mode contract must retain the fixed required sources YouTube, X, Reddit, and Web.",
        })
    if payload.get("required_sources") != list(CORE_REQUIRED_SOURCES):
        blockers.append({
            "code": "status_required_source_contract_mismatch",
            "message": "Source status must declare the fixed required sources in canonical order.",
        })

    required_families = [
        family.get("id")
        for family in plan.get("query_families", [])
        if isinstance(family, dict) and family.get("required", True) and isinstance(family.get("id"), str)
    ]
    executed_raw = payload.get("query_families_executed", [])
    executed = list(dict.fromkeys(value for value in executed_raw if isinstance(value, str))) if isinstance(executed_raw, list) else []
    contract["query_families_required"] = required_families
    contract["query_families_executed"] = executed
    missing_families = [family for family in required_families if family not in executed]
    if missing_families:
        blockers.append({
            "code": "query_family_not_executed",
            "message": "The selected mode has query families without an execution receipt: " + ", ".join(missing_families),
        })

    minimums = _mode_minimums(plan)
    contract["minimums"] = minimums
    for source, minimum in minimums.items():
        record = by_source.get(source)
        actual = _mode_evidence_count(record, source) if record is not None else 0
        if actual < minimum:
            blockers.append({
                "code": "mode_minimum_not_met",
                "source": source,
                "minimum": str(minimum),
                "actual": str(actual),
                "message": f"{source} has {actual} eligible evidence items; {expected_mode} requires at least {minimum}.",
            })
    contract["valid"] = not blockers
    return blockers, contract


def validate(
    payload: dict[str, Any],
    required_sources: list[str],
    *,
    require_complete: bool = False,
    plan: dict[str, Any] | None = None,
    require_mode_contract: bool = False,
) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    records = payload.get("sources")
    if not isinstance(records, list):
        return {"valid": False, "research_incomplete": True, "blockers": [{"code": "missing_sources", "message": "The packet has no sources array."}]}

    normalized_required_sources = list(dict.fromkeys(required_sources))
    required_set = set(normalized_required_sources)
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
        if status == "planned" and source in required_set:
            blockers.append({"code": "planned_not_retrieved", "message": f"{source} is only planned, not retrieved."})

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

    strict_core4 = require_complete or require_mode_contract
    if strict_core4:
        # This is deliberately separate from the backwards-compatible
        # --require-source behavior above. Partial source records are useful for
        # diagnostics, but they must never become a completed four-media brief.
        for source in CORE_REQUIRED_SOURCES:
            blockers.extend(_validate_core_source(by_source.get(source), source))

    mode_contract = None
    if require_mode_contract:
        mode_blockers, mode_contract = _validate_mode_contract(payload, by_source, plan)
        blockers.extend(mode_blockers)

    result = {
        "valid": not blockers,
        "research_incomplete": bool(blockers),
        "checked_at": _now(),
        "required_sources": list(CORE_REQUIRED_SOURCES) if strict_core4 else normalized_required_sources,
        "blockers": blockers,
    }
    if strict_core4:
        result["completion_contract"] = CORE_COMPLETION_CONTRACT
    if mode_contract is not None:
        result["mode_contract"] = mode_contract
        result["research_mode"] = mode_contract.get("mode")
    if isinstance(payload.get("run_id"), str):
        result["run_id"] = payload["run_id"]
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
    parser.add_argument("--plan", help="Exact research-plan.json used for selected-mode validation.")
    parser.add_argument(
        "--require-mode-contract",
        action="store_true",
        help="Require plan/status mode identity, query-family receipts, and mode-specific evidence floors.",
    )
    parser.add_argument("--out", help="Optional validation JSON path.")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("input must be a JSON object")
    plan = None
    if args.plan:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise SystemExit("plan must be a JSON object")
    result = validate(
        payload,
        list(CORE_REQUIRED_SOURCES) if args.require_core_4 else args.require_source,
        require_complete=args.require_core_4,
        plan=plan,
        require_mode_contract=args.require_mode_contract,
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
