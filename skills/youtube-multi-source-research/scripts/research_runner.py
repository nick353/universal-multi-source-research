#!/usr/bin/env python3
"""Common orchestration ledger for Universal Multi-Source Research.

The runner deliberately does not contain provider credentials or pretend to
fetch a source.  Source adapters (Web, YouTube, X, Reddit, and optional
platform adapters) return a source-status packet; this command owns the
shared run id, fixed core-source order, mode metadata, query-family ledger,
and fail-closed final validation.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from plan_research import MODE_NAMES, build_plan
from render_coverage import render
from validate_research_evidence import (
    CORE_COMPLETION_CONTRACT,
    CORE_REQUIRED_SOURCES,
    validate,
)


RUN_CONTRACT_VERSION = "universal_research_run.v1"
TERMINAL_STATUSES = {
    "complete",
    "partial",
    "auth_required",
    "blocked",
    "no_results",
    "not_configured",
    "error",
}
DEFAULT_ORCHESTRATION_MODE = "adapter_neutral"
PROTECTED_STATUS_FIELDS = {
    "contract_version",
    "run_id",
    "research_mode",
    "mode",
    "mode_selection",
    "required_sources",
    "source_order",
    "completion_contract",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_id(value: str | None) -> str:
    return value.strip() if value and value.strip() else f"research-{uuid.uuid4().hex}"


def _paths(work_dir: Path) -> dict[str, Path]:
    return {
        "plan": work_dir / "research-plan.json",
        "status": work_dir / "source-status.json",
        "run": work_dir / "research-run.json",
        "validation": work_dir / "research-validation.json",
        "coverage": work_dir / "coverage.md",
    }


def _ordered_sources(plan: dict[str, Any]) -> list[str]:
    planned = [
        record.get("source")
        for record in plan.get("sources", [])
        if isinstance(record, dict) and isinstance(record.get("source"), str)
    ]
    return list(CORE_REQUIRED_SOURCES) + [
        source for source in planned if source not in CORE_REQUIRED_SOURCES
    ]


def _source_template(plan_record: dict[str, Any]) -> dict[str, Any]:
    source = str(plan_record["source"])
    record: dict[str, Any] = {
        "source": source,
        "status": "planned",
        "count": 0,
        "evidence_urls": [],
        "reason": "not started; source adapter has not returned a terminal result",
        "retrieval_method": "",
        "runner_executed": False,
        "terminal_success": False,
        "evidence_retrieved": False,
        "approval_required": False,
        "approval_prompted": False,
        "selection_role": plan_record.get("selection_role"),
        "collection_limits": plan_record.get("collection_limits", {}),
    }
    if source == "youtube":
        record["usable_count"] = 0
    return record


def _initial_status(plan: dict[str, Any], run_id: str, orchestration_mode: str) -> dict[str, Any]:
    source_records = {
        str(record["source"]): _source_template(record)
        for record in plan.get("sources", [])
        if isinstance(record, dict) and record.get("source")
    }
    ordered = _ordered_sources(plan)
    sources = [source_records[source] for source in ordered if source in source_records]
    return {
        "contract_version": RUN_CONTRACT_VERSION,
        "run_id": run_id,
        "question": plan.get("question", ""),
        "research_mode": plan["mode"],
        "mode": plan["mode"],
        "mode_selection": plan.get("mode_selection", {}),
        "orchestration_mode": orchestration_mode,
        "required_sources": list(CORE_REQUIRED_SOURCES),
        "source_order": list(CORE_REQUIRED_SOURCES),
        "completion_contract": CORE_COMPLETION_CONTRACT,
        "query_families_required": [
            family["id"]
            for family in plan.get("query_families", [])
            if isinstance(family, dict) and family.get("required", True)
        ],
        "query_families_executed": [],
        "sources": sources,
        "overall_status": "research_incomplete",
        "started_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "validation_summary": None,
    }


def _run_metadata(plan: dict[str, Any], run_id: str, orchestration_mode: str) -> dict[str, Any]:
    return {
        "contract_version": RUN_CONTRACT_VERSION,
        "run_id": run_id,
        "research_mode": plan["mode"],
        "mode_selection": plan.get("mode_selection", {}),
        "orchestration_mode": orchestration_mode,
        "required_sources": list(CORE_REQUIRED_SOURCES),
        "source_order": list(CORE_REQUIRED_SOURCES),
        "completion_contract": CORE_COMPLETION_CONTRACT,
        "paths": {
            "plan": "research-plan.json",
            "status": "source-status.json",
            "validation": "research-validation.json",
            "coverage": "coverage.md",
        },
        "status": "research_incomplete",
        "created_at": _now(),
        "updated_at": _now(),
    }


def _load_run(work_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    paths = _paths(work_dir)
    plan = _read_json(paths["plan"])
    status = _read_json(paths["status"])
    if plan.get("run_id") != status.get("run_id"):
        raise ValueError("research-plan.json and source-status.json have different run_id values")
    if status.get("contract_version") != RUN_CONTRACT_VERSION:
        raise ValueError("source-status.json was not created by the common runner contract")
    if status.get("completed_at"):
        raise ValueError("research run is already finalized; start a new run to change its evidence")
    return plan, status, paths


def _records_by_source(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = status.get("sources")
    if not isinstance(records, list):
        raise ValueError("source-status.json must contain a sources array")
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not record.get("source"):
            raise ValueError("source-status.json contains an invalid source record")
        result[str(record["source"])] = record
    return result


def _next_core_source(status: dict[str, Any]) -> str | None:
    records = _records_by_source(status)
    for source in CORE_REQUIRED_SOURCES:
        if str(records.get(source, {}).get("status", "planned")) == "planned":
            return source
    return None


def _packet_record(packet: dict[str, Any], source: str) -> dict[str, Any]:
    if isinstance(packet.get("sources"), list):
        matches = [record for record in packet["sources"] if isinstance(record, dict) and record.get("source") == source]
        if len(matches) != 1:
            raise ValueError(f"source packet must contain exactly one record for {source}")
        return dict(matches[0])
    if packet.get("source") not in {None, source}:
        raise ValueError(f"source packet is for {packet.get('source')!r}, not {source!r}")
    record = dict(packet)
    record["source"] = source
    return record


def _merge_query_families(status: dict[str, Any], packet: dict[str, Any], extra: list[str]) -> None:
    current = status.get("query_families_executed", [])
    if not isinstance(current, list):
        current = []
    values = list(current)
    packet_values = packet.get("query_families_executed", [])
    allowed = set(value for value in status.get("query_families_required", []) if isinstance(value, str))
    incoming_values = []
    if isinstance(packet_values, list):
        incoming_values.extend(value for value in packet_values if isinstance(value, str))
    incoming_values.extend(extra)
    unknown = [value for value in incoming_values if value not in allowed]
    if unknown:
        raise ValueError("query-family receipt is not present in the selected plan: " + ", ".join(dict.fromkeys(unknown)))
    values.extend(incoming_values)
    status["query_families_executed"] = list(dict.fromkeys(value for value in values if value.strip()))


def command_start(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir).expanduser()
    work_dir.mkdir(parents=True, exist_ok=True)
    paths = _paths(work_dir)
    existing = [str(path.name) for path in paths.values() if path.exists()]
    if existing and not args.force:
        raise ValueError("work-dir already contains a run; use --force only to replace: " + ", ".join(existing))
    plan = build_plan(args.question, args.urls, args.window_days, args.mode)
    run_id = _run_id(args.run_id)
    plan["contract_version"] = RUN_CONTRACT_VERSION
    plan["run_id"] = run_id
    plan["research_mode"] = plan["mode"]
    plan["source_order"] = list(CORE_REQUIRED_SOURCES)
    plan["runner"] = "research_runner.py"
    _write_json(paths["plan"], plan)
    status = _initial_status(plan, run_id, args.orchestration_mode)
    _write_json(paths["status"], status)
    _write_json(paths["run"], _run_metadata(plan, run_id, args.orchestration_mode))
    print(json.dumps({
        "started": True,
        "run_id": run_id,
        "research_mode": plan["mode"],
        "required_sources": list(CORE_REQUIRED_SOURCES),
        "source_order": list(CORE_REQUIRED_SOURCES),
        "status": "research_incomplete",
        "work_dir": str(work_dir.resolve()),
    }, ensure_ascii=False))
    return 0


def command_record(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir).expanduser()
    plan, status, paths = _load_run(work_dir)
    source = args.source.strip().lower()
    records = _records_by_source(status)
    if source not in records:
        raise ValueError(f"{source} is not present in the research plan")
    if source in CORE_REQUIRED_SOURCES:
        next_source = _next_core_source(status)
        if next_source != source:
            raise ValueError(f"fixed core-source order violation: expected {next_source}, received {source}")
    packet = _read_json(Path(args.packet).expanduser())
    packet_run_id = packet.get("run_id")
    if packet_run_id is not None and packet_run_id != status.get("run_id"):
        raise ValueError(f"source packet run_id {packet_run_id!r} does not match run {status.get('run_id')!r}")
    incoming = _packet_record(packet, source)
    protected = sorted(PROTECTED_STATUS_FIELDS.intersection(incoming))
    if protected:
        raise ValueError("source packet may not override run metadata: " + ", ".join(protected))
    incoming_status = str(incoming.get("status", ""))
    if incoming_status not in TERMINAL_STATUSES:
        raise ValueError(f"{source} must be recorded with a terminal status, not {incoming_status or 'missing'}")
    merged = dict(records[source])
    merged.update(incoming)
    merged["source"] = source
    merged["recorded_at"] = _now()
    merged["approval_required"] = False
    merged["approval_prompted"] = False
    records[source] = merged
    ordered = [records[str(record["source"])] for record in status["sources"]]
    status["sources"] = ordered
    _merge_query_families(status, incoming, args.query_family or [])
    status["last_recorded_source"] = source
    status["updated_at"] = _now()
    status["overall_status"] = "research_incomplete"
    _write_json(paths["status"], status)
    run = _read_json(paths["run"]) if paths["run"].exists() else _run_metadata(plan, status["run_id"], DEFAULT_ORCHESTRATION_MODE)
    run["updated_at"] = _now()
    run["status"] = "research_incomplete"
    _write_json(paths["run"], run)
    print(json.dumps({
        "recorded": True,
        "run_id": status["run_id"],
        "source": source,
        "source_status": merged["status"],
        "next_required_source": _next_core_source(status),
        "status": "research_incomplete",
    }, ensure_ascii=False))
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    work_dir = Path(args.work_dir).expanduser()
    plan, status, paths = _load_run(work_dir)
    if args.query_family:
        _merge_query_families(status, {}, args.query_family)
    result = validate(
        status,
        list(CORE_REQUIRED_SOURCES),
        require_complete=True,
        plan=plan,
        require_mode_contract=True,
    )
    result.update({
        "contract_version": RUN_CONTRACT_VERSION,
        "run_id": status["run_id"],
        "research_mode": plan.get("mode"),
    })
    _write_json(paths["validation"], result)
    paths["coverage"].write_text(render(status), encoding="utf-8")
    status["validation_summary"] = {
        "valid": result["valid"],
        "blocker_count": len(result.get("blockers", [])),
        "validation_path": str(paths["validation"].resolve()),
    }
    status["overall_status"] = "complete" if result["valid"] else "research_incomplete"
    status["updated_at"] = _now()
    status["completed_at"] = _now()
    _write_json(paths["status"], status)
    run = _read_json(paths["run"]) if paths["run"].exists() else _run_metadata(plan, status["run_id"], DEFAULT_ORCHESTRATION_MODE)
    run["status"] = status["overall_status"]
    run["updated_at"] = _now()
    run["validation"] = result
    _write_json(paths["run"], run)
    print(json.dumps({
        "finalized": True,
        "run_id": status["run_id"],
        "research_mode": plan.get("mode"),
        "status": status["overall_status"],
        "valid": result["valid"],
        "validation": str(paths["validation"].resolve()),
        "coverage": str(paths["coverage"].resolve()),
        "blockers": result.get("blockers", []),
    }, ensure_ascii=False))
    return 0 if result["valid"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create one plan/status ledger before source retrieval")
    start.add_argument("urls", nargs="*", help="Seed URLs")
    start.add_argument("--question", default="", help="Research question or topic")
    start.add_argument("--window-days", type=int, default=30)
    start.add_argument("--mode", choices=["auto", *MODE_NAMES], default="auto")
    start.add_argument("--work-dir", required=True)
    start.add_argument("--run-id")
    start.add_argument("--orchestration-mode", default=DEFAULT_ORCHESTRATION_MODE)
    start.add_argument("--force", action="store_true", help="Replace an existing local run ledger explicitly")
    start.set_defaults(handler=command_start)

    record = subparsers.add_parser("record", help="Record one adapter's terminal source-status packet")
    record.add_argument("--work-dir", required=True)
    record.add_argument("--source", required=True)
    record.add_argument("--packet", required=True)
    record.add_argument("--query-family", action="append", default=[])
    record.set_defaults(handler=command_record)

    finalize = subparsers.add_parser("finalize", help="Validate mode, query ledger, and fixed core-four evidence")
    finalize.add_argument("--work-dir", required=True)
    finalize.add_argument("--query-family", action="append", default=[])
    finalize.set_defaults(handler=command_finalize)

    args = parser.parse_args()
    try:
        return int(args.handler(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "status": "research_incomplete"}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
