#!/usr/bin/env python3
"""Run the mandatory live X/Reddit admission gate for a research run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_SOURCES = ("x", "reddit")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback
    return value if isinstance(value, dict) else fallback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="The same query family used for collection.")
    parser.add_argument("--out", required=True, help="Output JSON admission packet path.")
    parser.add_argument("--command", default="opencli", help="OpenCLI executable name or absolute path.")
    parser.add_argument("--timeout", type=int, default=45, help="Per-source live probe timeout in seconds.")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    probe_script = Path(__file__).with_name("live_source_probe.py")
    validator_script = Path(__file__).with_name("validate_research_evidence.py")
    probe_exit_code: int | None = None
    with tempfile.TemporaryDirectory(prefix="research-gate-", dir=output.parent) as temp_dir:
        temp = Path(temp_dir)
        probe_path = temp / "live-source-probe.json"
        validation_path = temp / "research-validation.json"
        command = [
            sys.executable,
            str(probe_script),
            "--source", "x",
            "--source", "reddit",
            "--query", args.query,
            "--command", args.command,
            "--timeout", str(args.timeout),
            "--out", str(probe_path),
        ]
        try:
            probe = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=(args.timeout * len(REQUIRED_SOURCES)) + 20,
            )
            probe_exit_code = probe.returncode
        except subprocess.TimeoutExpired:
            probe_exit_code = 124

        packet = read_json(probe_path, {"version": 1, "sources": []})
        if probe_exit_code == 0 and probe_path.exists():
            validation_command = [
                sys.executable,
                str(validator_script),
                "--input", str(probe_path),
                "--require-source", "x",
                "--require-source", "reddit",
                "--out", str(validation_path),
            ]
            validation_run = subprocess.run(
                validation_command,
                capture_output=True,
                text=True,
                check=False,
            )
            validation = read_json(
                validation_path,
                {
                    "valid": False,
                    "research_incomplete": True,
                    "blockers": [{"code": "validation_output_missing"}],
                },
            )
            validation["validator_exit_code"] = validation_run.returncode
        else:
            validation = {
                "valid": False,
                "research_incomplete": True,
                "required_sources": list(REQUIRED_SOURCES),
                "blockers": [{
                    "code": "live_gate_failed",
                    "reason": "The X/Reddit live retrieval probe did not complete.",
                }],
            }

    valid = validation.get("valid") is True and validation.get("research_incomplete") is not True
    result = {
        "version": 1,
        "gate": "x_reddit_live_retrieval",
        "retrieved_at": now_iso(),
        "query": args.query,
        "read_only": True,
        "required_sources": list(REQUIRED_SOURCES),
        "sources": packet.get("sources", []),
        "validation": validation,
        "status": "ready" if valid else "research_incomplete",
        "probe_exit_code": probe_exit_code,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(output), "status": result["status"]}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
