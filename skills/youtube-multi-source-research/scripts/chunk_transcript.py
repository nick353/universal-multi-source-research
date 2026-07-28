#!/usr/bin/env python3
"""Split timestamped transcript JSON into bounded, model-ready chunks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_segments(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("segments", value.get("snippets", value.get("data", [])))
    if not isinstance(value, list):
        raise ValueError("Transcript JSON must be a list or contain segments/snippets/data")
    return [item for item in value if isinstance(item, dict) and str(item.get("text", "")).strip()]


def chunk(segments: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    length = 0

    def flush() -> None:
        nonlocal current, length
        if not current:
            return
        start = float(current[0].get("start", 0.0))
        end = float(current[-1].get("start", 0.0)) + float(current[-1].get("duration", 0.0))
        chunks.append(
            {
                "chunk_id": f"chunk-{len(chunks) + 1:04d}",
                "start": start,
                "end": end,
                "text": " ".join(str(item["text"]).strip() for item in current),
                "segment_count": len(current),
            }
        )
        current = []
        length = 0

    for segment in segments:
        text = str(segment["text"]).strip()
        if current and length + len(text) + 1 > max_chars:
            flush()
        current.append(segment)
        length += len(text) + (1 if length else 0)
    flush()
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-chars", type=int, default=12000)
    args = parser.parse_args()
    if args.max_chars < 100:
        parser.error("--max-chars must be at least 100")
    output = chunk(load_segments(args.input), args.max_chars)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chunks": len(output), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
