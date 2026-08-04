#!/usr/bin/env python3
"""Render Agent-Reach health data with English operational messages.

Agent-Reach currently emits some channel names and diagnostics in Chinese.
Keep its machine-readable status codes, but translate the display boundary so
the research Skill does not expose upstream locale text or credential-bearing
details to the user.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from typing import Any


SOURCE_LABELS = {
    "github": "GitHub repositories and code",
    "twitter": "Twitter/X posts",
    "youtube": "YouTube videos and subtitles",
    "reddit": "Reddit posts and comments",
    "facebook": "Facebook posts, pages, and groups",
    "instagram": "Instagram profiles and posts",
    "bilibili": "Bilibili videos, subtitles, and search",
    "xiaohongshu": "Xiaohongshu notes",
    "linkedin": "LinkedIn",
    "xiaoyuzhou": "Xiaoyuzhou podcast transcription",
    "v2ex": "V2EX topics and replies",
    "xueqiu": "Xueqiu market data and community posts",
    "rss": "RSS/Atom feeds",
    "exa_search": "Semantic web search",
    "web": "Web pages",
}

BACKEND_LABELS = {
    "twitter-cli": "twitter-cli",
    "OpenCLI": "OpenCLI",
    "rdt-cli": "rdt-cli",
    "yt-dlp": "yt-dlp",
    "Jina Reader": "Jina Reader",
    "feedparser": "feedparser",
    "gh CLI": "gh CLI",
    "V2EX API (public)": "V2EX public API",
    "Exa via mcporter": "Exa via mcporter",
}

SOURCE_MESSAGES = {
    "github": {
        "ok": "Public repositories and code are available.",
        "warn": "GitHub CLI is installed, but authentication was not live-verified.",
        "off": "GitHub CLI is not configured.",
    },
    "twitter": {
        "ok": "Twitter/X posts are available.",
        "warn": "Twitter/X access is installed but needs explicit credentials or a connected browser session.",
        "off": "Twitter/X access is not configured.",
    },
    "youtube": {
        "ok": "Video metadata and subtitles are available through yt-dlp.",
        "warn": "YouTube access is installed but needs additional runtime configuration.",
        "off": "YouTube access is not configured.",
    },
    "reddit": {
        "ok": "Reddit posts and comments are available.",
        "warn": "Reddit access needs a connected browser session or an authenticated read-only client.",
        "off": "Reddit access is not configured.",
    },
    "web": {
        "ok": "Web pages can be read through Jina Reader.",
        "warn": "Web page reading needs additional configuration.",
        "off": "Web page reading is not configured.",
    },
    "rss": {
        "ok": "RSS and Atom feeds are readable.",
        "warn": "RSS/Atom support needs the feedparser package.",
        "off": "RSS/Atom support is not configured.",
    },
    "exa_search": {
        "ok": "Semantic web search is available.",
        "warn": "Exa is configured, but remote connectivity was not live-verified.",
        "off": "Semantic web search is not configured.",
    },
    "v2ex": {
        "ok": "The public V2EX API is available.",
        "warn": "The V2EX API is installed but not currently available.",
        "off": "V2EX access is not configured.",
    },
    "bilibili": {
        "ok": "Bilibili search is available.",
        "warn": "Bilibili access is installed but needs additional configuration.",
        "off": "Bilibili access is not configured.",
    },
    "facebook": {
        "warn": "The browser bridge is installed, but no connected browser extension was detected.",
        "off": "Facebook access is not configured.",
    },
    "instagram": {
        "warn": "The browser bridge is installed, but no connected browser extension was detected.",
        "off": "Instagram access is not configured.",
    },
    "xiaohongshu": {
        "warn": "The browser bridge is installed, but no connected browser extension was detected.",
        "off": "Xiaohongshu access is not configured.",
    },
    "linkedin": {
        "warn": "LinkedIn access is not configured or was not live-verified.",
        "off": "LinkedIn access is not configured.",
    },
    "xiaoyuzhou": {
        "ok": "Podcast download and transcription are available.",
        "warn": "Podcast transcription needs additional configuration.",
        "off": "Podcast transcription is not configured.",
    },
    "xueqiu": {
        "ok": "Xueqiu access is available.",
        "warn": "Xueqiu access needs a login cookie or is currently unavailable.",
        "off": "Xueqiu access is not configured.",
    },
}


BACKEND_FALLBACKS = {
    "bilibili": "Bilibili Search API",
    "xiaohongshu": "Xiaohongshu",
    "xiaoyuzhou": "Xiaoyuzhou podcast transcription",
    "twitter": "Twitter/X client",
    "reddit": "Reddit client",
}


def _english_backend(value: Any, source: str) -> str:
    text = str(value)
    translated = BACKEND_LABELS.get(text, text)
    return translated if not re.search(r"[\u3400-\u9fff]", translated) else BACKEND_FALLBACKS.get(source, "Configured backend")


def _english_message(source: str, status: str, backends: list[str] | None = None) -> str:
    if status == "warn" and source in {"twitter", "reddit"} and "OpenCLI" in (backends or []):
        return "OpenCLI is configured; run the read-only source smoke test before collection."
    message = SOURCE_MESSAGES.get(source, {}).get(status)
    if message:
        return message
    if status == "ok":
        return "Available."
    if status in {"warn", "auth_required", "not_configured"}:
        return "Installed but requires configuration or login."
    if status in {"off", "no_results"}:
        return "Not configured or no result was available."
    if status == "blocked":
        return "Access was blocked by the source."
    return "The health check failed."


def _effective_status(source: str, status: str, backends: list[str]) -> str:
    """Expose the actionable state without weakening the upstream status code."""
    if status == "ok":
        return "available"
    if status == "warn" and source in {"twitter", "reddit"} and "OpenCLI" in backends:
        return "configured_unverified"
    return status


def translate_results(results: dict[str, Any]) -> dict[str, Any]:
    """Translate display fields while preserving stable status fields."""
    translated: dict[str, Any] = {}
    for source, record in results.items():
        if not isinstance(record, dict):
            translated[source] = {
                "status": "error",
                "name": SOURCE_LABELS.get(source, source),
                "message": "The health check returned an invalid result.",
            }
            continue
        status = str(record.get("status", "error"))
        backends = [_english_backend(item, source) for item in record.get("backends", [])]
        effective_status = _effective_status(source, status, backends)
        translated[source] = {
            "status": status,
            "name": SOURCE_LABELS.get(source, source.replace("_", " ").title()),
            "message": _english_message(source, status, backends),
            "tier": record.get("tier"),
            "backends": backends,
            "active_backend": _english_backend(record["active_backend"], source)
            if record.get("active_backend")
            else None,
            "effective_status": effective_status,
            "verification": {
                "required": effective_status == "configured_unverified",
                "backend": "OpenCLI" if effective_status == "configured_unverified" else None,
                "read_only_probe": effective_status == "configured_unverified",
            },
        }
    return translated


def run_doctor(command: str = "agent-reach") -> tuple[dict[str, Any], int]:
    executable = shutil.which(command) or command
    try:
        result = subprocess.run(
            [executable, "doctor", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "error",
            "message": "Could not run Agent-Reach doctor.",
            "details": "The upstream error details were not exposed.",
            "sources": {},
        }, 1
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Agent-Reach doctor returned invalid JSON.",
            "details": "The upstream output was not exposed.",
            "sources": {},
        }, result.returncode or 1
    if not isinstance(raw, dict):
        return {
            "status": "error",
            "message": "Agent-Reach doctor returned an invalid object.",
            "sources": {},
        }, result.returncode or 1
    return {"status": "ok" if result.returncode == 0 else "error", "sources": translate_results(raw)}, result.returncode


def render_text(payload: dict[str, Any]) -> str:
    if payload.get("status") == "error" and not payload.get("sources"):
        return f"Agent Reach Status\n==================\nError: {payload.get('message', 'Unknown error.')}\n"
    sources = payload.get("sources", {})
    lines = ["Agent Reach Status", "==================", ""]
    ok_count = 0
    for source, record in sources.items():
        status = record.get("status", "error")
        if status == "ok":
            ok_count += 1
        lines.append(f"- {record.get('name', source)}: {status} — {record.get('message', '')}")
    lines.extend(["", f"Status: {ok_count}/{len(sources)} sources available."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Agent-Reach status in English.")
    parser.add_argument("--json", action="store_true", help="Output translated machine-readable JSON.")
    parser.add_argument("--command", default="agent-reach", help="Agent-Reach executable name or path.")
    args = parser.parse_args()
    payload, returncode = run_doctor(args.command)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(payload), end="")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
