#!/usr/bin/env python3
"""Save a research brief to the stable Universal Research report directory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path


DEFAULT_REPORT_DIR = Path.home() / "Documents" / "Codex" / "Universal Research" / "reports"
SAFE_ARTIFACT_SUFFIXES = {".json", ".jsonl", ".md", ".srt", ".txt", ".vtt"}
CORE_REQUIRED_SOURCES = ("youtube", "x", "reddit", "web")
CORE_COMPLETION_CONTRACT = "core4_strict_v1"


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\-\u3040-\u30ff\u3400-\u9fff ]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value.strip())
    return (value[:80].strip("-") or "research-brief").lower()


def combine(coverage: str, report: str) -> str:
    coverage = coverage.strip()
    report = report.lstrip()
    if coverage and report.startswith("## 調査状況"):
        return report.rstrip() + "\n"
    if coverage:
        return coverage.rstrip() + "\n\n" + report.rstrip() + "\n"
    return report.rstrip() + "\n"


def choose_package_path(directory: Path, topic: str, now: datetime) -> Path:
    stamp = now.astimezone().strftime("%Y%m%d-%H%M%S")
    base = directory / f"{stamp}-{slugify(topic)}"
    candidate = base
    index = 2
    while candidate.exists():
        candidate = directory / f"{stamp}-{slugify(topic)}-{index}"
        index += 1
    return candidate


def copy_transcript_artifacts(source: Path, output: Path) -> Path | None:
    """Copy only transcript-like artifacts and return their destination."""
    if not source.exists() or not source.is_dir():
        return None
    destination = output.parent / "artifacts" / "youtube"
    copied = 0
    for item in source.rglob("*"):
        if not item.is_file() or item.suffix.lower() not in SAFE_ARTIFACT_SUFFIXES:
            continue
        relative = item.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        copied += 1
    if not copied:
        return None
    return destination.parent


def _is_strict_core4_success(validation: dict) -> bool:
    """Only the fixed four-media validation contract may be saved as complete."""
    required = validation.get("required_sources")
    return (
        validation.get("valid") is True
        and validation.get("research_incomplete") is not True
        and validation.get("completion_contract") == CORE_COMPLETION_CONTRACT
        and isinstance(required, list)
        and required == list(CORE_REQUIRED_SOURCES)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Completed research brief Markdown")
    parser.add_argument("--coverage", help="Rendered source coverage Markdown")
    parser.add_argument("--topic", required=True, help="Short topic used for the filename")
    parser.add_argument("--report-dir", help="Override the stable report directory for tests or local policy")
    parser.add_argument("--artifacts-dir", help="Transcript artifact directory, normally work/youtube")
    parser.add_argument("--validation", required=True, help="Research evidence validation JSON")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Save an explicitly partial report when validation fails; never claim it is complete.",
    )
    parser.add_argument("--output", help="Explicit output path")
    args = parser.parse_args()

    validation = json.loads(Path(args.validation).read_text(encoding="utf-8"))
    validation_valid = _is_strict_core4_success(validation)
    if not validation_valid and not args.allow_partial:
        print(json.dumps({
            "saved": False,
            "research_incomplete": True,
            "reason": "Research evidence validation failed; pass --allow-partial only for an explicitly partial report.",
        }, ensure_ascii=False))
        return 1

    report = Path(args.input).read_text(encoding="utf-8")
    coverage = Path(args.coverage).read_text(encoding="utf-8") if args.coverage else ""
    configured_dir = os.environ.get("UNIVERSAL_RESEARCH_REPORT_DIR")
    directory = Path(args.report_dir or configured_dir or DEFAULT_REPORT_DIR).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    if args.output:
        output = Path(args.output).expanduser()
    else:
        package = choose_package_path(directory, args.topic, datetime.now().astimezone())
        package.mkdir(parents=True, exist_ok=True)
        output = package / "report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(combine(coverage, report), encoding="utf-8")
    artifacts = copy_transcript_artifacts(Path(args.artifacts_dir).expanduser(), output) if args.artifacts_dir else None
    result = {
        "saved": True,
        "research_incomplete": not validation_valid,
        "path": str(output.resolve()),
        "package_path": str(output.parent.resolve()),
        "directory": str(output.parent.resolve()),
        "artifacts_path": str(artifacts.resolve()) if artifacts else None,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
