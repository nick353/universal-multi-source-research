#!/usr/bin/env python3
"""Run a bounded, read-only live smoke search for configured community sources.

This is an acquisition check, not a substitute for collecting and opening the
returned records.  It intentionally stores only safe metadata and source URLs;
post bodies, credentials, and upstream stderr are never persisted.
"""

from __future__ import annotations

import argparse
import json
import os
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
FALLBACK_COMMANDS = {
    "x": (("twitter-cli", "twitter"),),
    "reddit": (("rdt-cli", "rdt"),),
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


def _adapter_command(source: str, query: str, backend: str, executable: str) -> list[str]:
    if backend == "OpenCLI":
        return [
            executable,
            *SOURCE_COMMANDS[source],
            query,
            "-f", "json",
            "--window", "background",
            "--site-session", "persistent",
        ]
    if backend == "twitter-cli":
        return ["twitter", "search", query, "--max", "10", "--json"]
    return ["rdt", "search", query, "--limit", "10"]


def _twitter_credentials() -> dict[str, str]:
    """Load Agent-Reach's stored X credentials only into a child env."""
    names = ("TWITTER_AUTH_TOKEN", "TWITTER_CT0")
    credentials = {name: os.environ[name] for name in names if os.environ.get(name)}
    if len(credentials) == len(names):
        return credentials
    config = Path.home() / ".agent-reach" / "config.yaml"
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except OSError:
        return credentials
    config_keys = {
        "TWITTER_AUTH_TOKEN": "twitter_auth_token",
        "TWITTER_CT0": "twitter_ct0",
    }
    for line in lines:
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        env_name = next((name for name, config_key in config_keys.items() if config_key == key), None)
        if env_name and env_name not in credentials:
            value = value.strip().strip("\"'")
            if value:
                credentials[env_name] = value
    return credentials


def _adapter_environment(backend: str) -> dict[str, str] | None:
    if backend != "twitter-cli":
        return None
    environment = os.environ.copy()
    environment.update(_twitter_credentials())
    return environment


def _record(
    source: str,
    status: str,
    reason: str,
    error_code: str,
    backend: str,
    configured: bool,
    started: float,
    attempts: list[dict[str, str]],
    **values: Any,
) -> dict[str, Any]:
    count = values.pop("count", 0)
    evidence_urls = values.pop("evidence_urls", [])
    content_records = values.get("content_records", 0)
    return {
        "source": source,
        "status": status,
        "count": count,
        "evidence_urls": evidence_urls,
        "retrieval_method": f"{backend} read-only search",
        "backend": backend,
        "reason": reason,
        "error_code": error_code,
        "configured": configured,
        "smoke_attempted": True,
        "smoke_result": status,
        "fallback_attempted": any(item["backend"] != "OpenCLI" for item in attempts),
        "evidence_retrieved": bool(evidence_urls and content_records),
        "attempts": attempts,
        "duration_ms": int((time.monotonic() - started) * 1000),
        **values,
    }


def probe_source(
    source: str,
    query: str,
    executable: str,
    timeout: int,
    configured: bool = True,
) -> dict[str, Any]:
    started = time.monotonic()
    candidates: list[tuple[str, str, bool]] = [("OpenCLI", executable, configured)]
    for backend, command_name in FALLBACK_COMMANDS.get(source, ()):
        candidates.append((backend, command_name, bool(shutil.which(command_name))))

    attempts: list[dict[str, str]] = []
    overall_configured = any(item[2] for item in candidates)
    for backend, command_name, available in candidates:
        if not available:
            continue
        command = _adapter_command(source, query, backend, command_name)
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                env=_adapter_environment(backend),
            )
        except subprocess.TimeoutExpired:
            attempts.append({"backend": backend, "status": "error", "error_code": "timeout"})
            continue
        except OSError:
            attempts.append({"backend": backend, "status": "not_configured", "error_code": "executable_unavailable"})
            continue

        if result.returncode != 0:
            status, reason = _failure_status(result.returncode, result.stderr)
            attempts.append({"backend": backend, "status": status, "error_code": f"exit_{result.returncode}"})
            continue

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            attempts.append({"backend": backend, "status": "error", "error_code": "invalid_json"})
            continue

        records = _items(payload)
        urls = _urls(records)
        content_count, matching_count, query_terms, minimum_matches = _content_stats(records, query)
        if not records:
            attempts.append({"backend": backend, "status": "no_results", "error_code": "no_results"})
            return _record(
                source, "no_results", "The read-only source search returned no records.", "no_results",
                backend, overall_configured, started, attempts,
                count=0, evidence_urls=[], content_records=0, topic_match_candidates=0,
                topic_terms=query_terms, topic_match_min_terms=minimum_matches,
            )
        if not urls:
            attempts.append({"backend": backend, "status": "partial", "error_code": "urls_missing"})
            return _record(
                source, "partial", "The source returned records but no stable source URLs were exposed.", "urls_missing",
                backend, overall_configured, started, attempts,
                count=len(records), evidence_urls=[], content_records=content_count,
                topic_match_candidates=matching_count, topic_terms=query_terms,
                topic_match_min_terms=minimum_matches,
            )
        if not content_count:
            attempts.append({"backend": backend, "status": "partial", "error_code": "content_missing"})
            return _record(
                source, "partial", "The source returned URLs but no readable source body was exposed.", "content_missing",
                backend, overall_configured, started, attempts,
                count=len(records), evidence_urls=urls, content_records=0,
                topic_match_candidates=matching_count, topic_terms=query_terms,
                topic_match_min_terms=minimum_matches,
            )
        attempts.append({"backend": backend, "status": "complete", "error_code": ""})
        return _record(
            source, "complete", "The read-only source search returned source-native records and URLs.", "",
            backend, overall_configured, started, attempts,
            count=len(records), evidence_urls=urls, content_records=content_count,
            topic_match_candidates=matching_count, topic_terms=query_terms,
            topic_match_min_terms=minimum_matches,
        )

    if attempts:
        last = attempts[-1]
        status = last["status"]
        reason = {
            "auth_required": "The read-only source search requires authentication.",
            "blocked": "The source rejected or rate-limited the read-only search.",
            "error": "All configured read-only source adapters failed.",
            "not_configured": "No usable read-only source adapter is configured.",
        }.get(status, "The read-only source search failed.")
        return _record(
            source, status, reason, last["error_code"], last["backend"], overall_configured,
            started, attempts,
        )
    return _record(
        source, "not_configured", "No usable read-only source adapter is configured.",
        "executable_unavailable", "OpenCLI", overall_configured, started, attempts,
    )


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

    executable = _executable(args.command)
    configured = bool(Path(executable).is_file() or shutil.which(executable))
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
            probe_source(source, args.query, executable, args.timeout, configured)
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
