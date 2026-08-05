#!/usr/bin/env python3
"""Normalize a local transcript or fetch a YouTube transcript through safe adapters.

The URL path is intentionally best-effort and read-only. It never falls back to
audio download unless --allow-audio is explicitly supplied.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[\.,]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[\.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_seconds(value: str) -> float:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_text(value: str) -> str:
    value = html.unescape(value.replace("\\n", "\n"))
    value = TAG_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_vtt_or_srt(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines):
        match = TIMESTAMP_RE.search(lines[index])
        if not match:
            index += 1
            continue
        start = timestamp_seconds(match.group("start"))
        end = timestamp_seconds(match.group("end"))
        index += 1
        body: list[str] = []
        while index < len(lines) and lines[index].strip():
            if not TIMESTAMP_RE.search(lines[index]):
                body.append(lines[index].strip())
            index += 1
        value = clean_text(" ".join(body))
        if value:
            segments.append({"text": value, "start": start, "duration": max(0.0, end - start)})
        index += 1
    return segments


def _segment_from_mapping(item: dict[str, Any]) -> dict[str, Any] | None:
    value = item.get("text") or item.get("content") or item.get("transcript") or ""
    if isinstance(value, list):
        value = " ".join(str(part) for part in value)
    value = clean_text(str(value))
    if not value:
        return None
    start_raw = item.get("start", item.get("start_time", 0.0))
    end_raw = item.get("end", item.get("end_time"))
    try:
        start = float(start_raw or 0.0)
    except (TypeError, ValueError):
        start = 0.0
    duration_raw = item.get("duration")
    try:
        duration = float(duration_raw) if duration_raw is not None else None
    except (TypeError, ValueError):
        duration = None
    if duration is None and end_raw is not None:
        try:
            duration = max(0.0, float(end_raw) - start)
        except (TypeError, ValueError):
            duration = 0.0
    return {"text": value, "start": start, "duration": duration or 0.0}


def parse_json_transcript(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [{"text": clean_text(value), "start": 0.0, "duration": 0.0}] if clean_text(value) else []
    if isinstance(value, dict):
        for key in ("segments", "snippets", "transcript", "data", "items"):
            if key in value:
                return parse_json_transcript(value[key])
        segment = _segment_from_mapping(value)
        return [segment] if segment else []
    if isinstance(value, list):
        segments: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                segment = _segment_from_mapping(item)
            else:
                segment = {"text": clean_text(str(item)), "start": 0.0, "duration": 0.0}
            if segment and segment["text"]:
                segments.append(segment)
        return segments
    return []


def parse_input(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix in {".vtt", ".srt"}:
        return parse_vtt_or_srt(raw), suffix.lstrip(".")
    if suffix == ".json":
        return parse_json_transcript(json.loads(raw)), "json"
    return ([{"text": clean_text(raw), "start": 0.0, "duration": 0.0}] if clean_text(raw) else []), "text"


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)


def remaining_timeout(deadline: float) -> int:
    return max(0, int(deadline - time.monotonic()))


def subtitle_languages(preferred: list[str]) -> list[str]:
    """Return ordered single-language attempts with reliable English fallbacks."""
    values = list(preferred or [])
    for fallback in ("en", "en-US", "en-GB"):
        if fallback not in values:
            values.append(fallback)
    return list(dict.fromkeys(values))


def fetch_yt_dlp_subtitles(
    yt_dlp: str,
    args: argparse.Namespace,
    raw_dir: Path,
    errors: list[str],
    deadline: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Try each subtitle language independently so one 429 does not abort the video."""
    subtitle_pattern = str(raw_dir / "%(id)s.%(ext)s")
    for language in subtitle_languages(args.lang):
        timeout = remaining_timeout(deadline)
        if timeout <= 0:
            errors.append("yt-dlp subtitle extraction timed out before the next language attempt")
            break
        before = set(raw_dir.glob("*"))
        socket_timeout = str(max(5, min(timeout, 30)))
        command = [
            yt_dlp,
            "--no-playlist",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            language,
            "--sub-format",
            "vtt/srt",
            "--socket-timeout",
            socket_timeout,
            "--output",
            subtitle_pattern,
            args.url,
        ]
        try:
            result = run_command(command, timeout)
            created = set(raw_dir.glob("*")) - before
            subtitle_files = sorted(
                path for path in created
                if path.suffix.lower() in {".vtt", ".srt"} and f".{language}." in path.name
            )
            if subtitle_files:
                chosen = subtitle_files[0]
                segments, input_kind = parse_input(chosen)
                if segments:
                    return segments, {
                        "source": "youtube",
                        "url": args.url,
                        "retrieved_at": now_iso(),
                        "language": language,
                        "transcript_type": "manual_or_generated",
                        "retrieval_method": "yt_dlp",
                        "input_kind": input_kind,
                        "raw_file": str(chosen.relative_to(args.out)),
                        "status": "complete",
                    }
            errors.append(f"yt-dlp subtitle extraction failed ({language}): exit={result.returncode}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"yt-dlp error ({language}): {type(exc).__name__}")
    return None


def save_transcript(out_dir: Path, segments: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    if not segments:
        raise ValueError("No transcript segments were found")
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized = []
    for segment in segments:
        normalized.append(
            {
                "text": segment["text"],
                "start": float(segment.get("start", 0.0)),
                "duration": float(segment.get("duration", 0.0)),
            }
        )
    (out_dir / "transcript.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Transcript", ""]
    for item in normalized:
        lines.append(f"[{item['start']:.2f}s] {item['text']}")
    (out_dir / "transcript.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_url(args: argparse.Namespace, out_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    deadline = time.monotonic() + max(1, args.timeout)

    yt_dlp = shutil.which("yt-dlp")
    agent_reach = shutil.which("agent-reach")
    # Prefer native subtitle retrieval in auto mode. It is faster, does not need
    # an ASR credential, and keeps the user's read-only/no-audio contract.
    if args.backend in {"auto", "yt-dlp"} and yt_dlp:
        result = fetch_yt_dlp_subtitles(yt_dlp, args, raw_dir, errors, deadline)
        if result:
            return result
    elif args.backend == "yt-dlp":
        errors.append("yt-dlp is not installed")

    # Agent-Reach transcribe is an ASR/audio route. Keep it explicit unless the
    # caller has opted into audio fallback, so auto mode cannot silently fetch audio.
    if args.backend == "agent-reach" or (args.backend == "auto" and args.allow_audio):
        if not agent_reach:
            errors.append("agent-reach is not installed")
        elif (timeout := remaining_timeout(deadline)) <= 0:
            errors.append("agent-reach skipped because the overall timeout expired")
        else:
            try:
                result = run_command([agent_reach, "transcribe", args.url], timeout)
                if result.returncode == 0 and result.stdout.strip():
                    output = result.stdout.strip()
                    try:
                        segments = parse_json_transcript(json.loads(output))
                        input_kind = "json"
                    except json.JSONDecodeError:
                        segments = [{"text": clean_text(output), "start": 0.0, "duration": 0.0}]
                        input_kind = "text"
                    if segments:
                        return segments, {
                            "source": "youtube",
                            "url": args.url,
                            "retrieved_at": now_iso(),
                            "language": args.lang[0] if args.lang else None,
                            "transcript_type": "asr_or_backend",
                            "retrieval_method": "agent_reach",
                            "input_kind": input_kind,
                            "status": "complete",
                        }
                errors.append(f"agent-reach failed: exit={result.returncode}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"agent-reach error: {type(exc).__name__}")

    if args.allow_audio:
        if not yt_dlp:
            errors.append("audio fallback requires yt-dlp")
        elif (timeout := remaining_timeout(deadline)) <= 0:
            errors.append("audio fallback skipped because the overall timeout expired")
        else:
            audio_pattern = str(raw_dir / "audio.%(ext)s")
            try:
                result = run_command([yt_dlp, "-x", "--audio-format", "wav", "--output", audio_pattern, args.url], timeout)
                audio_files = list(raw_dir.glob("audio.*"))
                if result.returncode == 0 and audio_files:
                    try:
                        from faster_whisper import WhisperModel  # type: ignore

                        model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
                        segments_iter, info = model.transcribe(str(audio_files[0]), language=args.lang[0] if args.lang else None, word_timestamps=False)
                        segments = [{"text": clean_text(s.text), "start": float(s.start), "duration": max(0.0, float(s.end) - float(s.start))} for s in segments_iter if clean_text(s.text)]
                        return segments, {
                            "source": "youtube",
                            "url": args.url,
                            "retrieved_at": now_iso(),
                            "language": getattr(info, "language", None),
                            "transcript_type": "asr",
                            "retrieval_method": "asr",
                            "model": args.model,
                            "status": "complete",
                        }
                    except ImportError:
                        errors.append("faster-whisper is not installed")
                    except Exception as exc:  # pragma: no cover - hardware/model dependent
                        errors.append(f"faster-whisper failed: {type(exc).__name__}")
                else:
                    errors.append(f"audio download failed: exit={result.returncode}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"audio download error: {type(exc).__name__}")

    raise RuntimeError("No transcript was obtained. " + "; ".join(errors or ["no compatible backend was found"]))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="YouTube URL")
    parser.add_argument("--input", type=Path, help="Local VTT, SRT, JSON, Markdown, or text transcript")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--lang", nargs="+", default=["ja", "en"], help="Preferred subtitle/ASR languages")
    parser.add_argument("--backend", choices=["auto", "agent-reach", "yt-dlp"], default="auto")
    parser.add_argument("--allow-audio", action="store_true", help="Explicitly allow audio download and ASR fallback")
    parser.add_argument("--model", default="small", help="faster-whisper model when --allow-audio is used")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="faster-whisper device")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type")
    parser.add_argument("--timeout", type=int, default=120, help="Overall URL fetch timeout in seconds")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if bool(args.url) == bool(args.input):
        print("Provide exactly one of URL or --input", file=sys.stderr)
        return 2
    try:
        if args.input:
            segments, input_kind = parse_input(args.input)
            manifest = {
                "source": "youtube" if "youtube" in str(args.input).lower() else "transcript_file",
                "retrieved_at": now_iso(),
                "transcript_type": "provided",
                "retrieval_method": "manual",
                "input_kind": input_kind,
                "input_file": str(args.input),
                "status": "complete",
            }
        else:
            segments, manifest = fetch_url(args, args.out)
        save_transcript(args.out, segments, manifest)
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
