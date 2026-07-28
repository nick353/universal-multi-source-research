#!/usr/bin/env python3
"""Create a deterministic cross-platform research plan from a question and URLs."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_SOURCES = ["youtube", "x", "reddit", "web", "github", "hacker_news", "rss"]
OPTIONAL_SOURCES = ["tiktok", "instagram", "bluesky", "linkedin", "arxiv", "polymarket", "bilibili", "xiaohongshu"]
QUERY_FAMILIES = [
    {"id": "exact", "label": "exact topic or entity", "suffix": "", "required": True},
    {"id": "japanese", "label": "Japanese variant", "suffix": " 日本語", "required": True},
    {"id": "english", "label": "English variant", "suffix": " English", "required": True},
    {"id": "synonyms", "label": "synonyms and related terms", "suffix": " synonyms related terms", "required": True},
    {"id": "official", "label": "official and primary sources", "suffix": " official primary source documentation", "required": True},
    {"id": "news", "label": "news and recent updates", "suffix": " latest news update", "required": True},
    {"id": "implementation", "label": "implementation and tutorial", "suffix": " tutorial implementation setup", "required": True},
    {"id": "experience", "label": "real-world experience and review", "suffix": " review real-world experience", "required": True},
    {"id": "criticism", "label": "criticism, limitations, and failures", "suffix": " criticism limitations problems failure", "required": True},
    {"id": "counterargument", "label": "counterargument and alternative view", "suffix": " counterargument alternative view debate", "required": True},
    {"id": "reddit_comments", "label": "Reddit comments and first-hand reports", "suffix": " site:reddit.com comments experience", "required": True},
    {"id": "github_discussions", "label": "GitHub Issues and Discussions", "suffix": " site:github.com issues discussions", "required": True},
]

SOURCE_TARGETS = {
    "youtube": ["5-10 diverse videos", "captions or transcripts", "metadata", "related claims"],
    "web": ["ordinary web search", "official pages", "documentation", "news", "blogs", "Q&A", "primary sources"],
    "reddit": ["submissions", "comments", "parent and reply context", "subreddit context", "linked sources"],
    "github": ["repositories", "releases", "Issues", "Discussions", "maintainers", "related repositories"],
    "x": ["posts", "threads", "replies", "quoted posts", "linked sources"],
}


def classify_url(value: str) -> str:
    host = (urlparse(value).hostname or "").lower()
    path = (urlparse(value).path or "").lower()
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return "youtube"
    if host == "x.com" or host.endswith(".x.com") or host == "twitter.com" or host.endswith(".twitter.com"):
        return "x"
    if host == "reddit.com" or host.endswith(".reddit.com") or host == "redd.it" or host.endswith(".redd.it"):
        return "reddit"
    if host == "github.com" or host.endswith(".github.com"):
        return "github"
    if path.endswith(".pdf"):
        return "web_pdf"
    return "web"


def source_expansion(seed_type: str) -> list[str]:
    expansions = {
        "youtube": ["youtube", "x", "reddit", "web", "github"],
        "x": ["x", "reddit", "youtube", "web", "github"],
        "reddit": ["reddit", "x", "youtube", "web", "github"],
        "github": ["github", "x", "reddit", "youtube", "web"],
        "web": ["web", "x", "reddit", "youtube", "github"],
        "web_pdf": ["web", "x", "reddit", "youtube", "github"],
    }
    return expansions.get(seed_type, DEFAULT_SOURCES[:])


def make_queries(question: str, urls: list[str]) -> list[str]:
    queries: list[str] = []
    base = question.strip()
    if base:
        for family in QUERY_FAMILIES:
            suffix = family["suffix"]
            queries.append(f"{base}{suffix if not suffix or suffix.startswith(' ') else ' ' + suffix}")
    for url in urls:
        parsed = urlparse(url)
        seed_type = classify_url(url)
        path_tokens = [part for part in parsed.path.strip("/").split("/") if part]
        if seed_type == "youtube":
            token = f"youtube {parsed.query}" if parsed.query else "youtube " + " ".join(path_tokens)
        elif seed_type == "x":
            token = "x " + " ".join(path_tokens[-3:])
        elif seed_type == "reddit":
            token = "reddit " + " ".join(path_tokens[-5:])
        else:
            token = " ".join(path_tokens) or parsed.netloc
        token = token.strip()
        if token:
            queries.append(token)
    return list(dict.fromkeys(queries))


def query_family_plan() -> list[dict]:
    return [
        {
            "id": family["id"],
            "label": family["label"],
            "required": family["required"],
            "agent_action": "Generate a natural-language Japanese/English variant or synonym rather than blindly appending the label." if family["id"] in {"japanese", "english", "synonyms"} else "Run this family against the relevant sources and preserve the results separately.",
        }
        for family in QUERY_FAMILIES
    ]


def build_plan(question: str, urls: list[str], window_days: int) -> dict:
    seeds = [{"url": url, "type": classify_url(url)} for url in urls]
    sources = list(DEFAULT_SOURCES)
    for seed in seeds:
        for source in source_expansion(seed["type"]):
            if source not in sources:
                sources.append(source)
    broad_request = bool(re.search(r"全プラットフォーム|全媒体|すべて|全部|万能|all platforms|every platform", question, re.I))
    if broad_request:
        sources.extend(source for source in OPTIONAL_SOURCES if source not in sources)
    source_records = [
        {
            "source": source,
            "status": "planned",
            "retrieval_role": {
                "web": "ordinary web search plus opening official pages, news, blogs, Q&A, and primary sources",
                "youtube": "multiple diverse videos, captions/transcripts, metadata, and related claims",
                "x": "posts, threads, replies, quotes, and linked sources",
                "reddit": "submissions, comments, subreddit context, and linked sources",
                "github": "repositories, releases, issues, discussions, and maintainers",
                "hacker_news": "technical discussions and linked primary sources",
                "rss": "recent feeds and source discovery",
            }.get(source, "relevant configured platform search and source retrieval"),
            "collection_targets": SOURCE_TARGETS.get(source, ["relevant configured platform search and source retrieval"]),
            "youtube_video_target": "5-10 diverse videos" if source == "youtube" else None,
        }
        for source in sources
    ]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "window_days": window_days,
        "seeds": seeds,
        "queries": make_queries(question, urls),
        "query_families": query_family_plan(),
        "sources": source_records,
        "youtube_policy": {
            "target_count": 5,
            "maximum_count": 10,
            "minimum_distinct_count": 3,
            "require_channel_diversity": True,
            "required_perspectives": ["official_or_primary", "specialist", "independent_experience", "recent_update", "counterpoint"],
            "expand_supplied_video_url": True,
        },
        "web_policy": {
            "ordinary_search_required": True,
            "required_result_roles": ["official", "primary", "news", "blog", "q_and_a"],
        },
        "community_policy": {
            "reddit_comments_required": True,
            "github_issues_required": True,
            "github_discussions_required": True,
        },
        "principles": [
            "A blocked or unconfigured source is not no_results.",
            "Repeated or copied content is not independent corroboration.",
            "Search snippets are leads; important claims require the original URL.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="Seed URLs")
    parser.add_argument("--question", default="", help="Research question or topic")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()
    plan = build_plan(args.question, args.urls, args.window_days)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(output), "sources": len(plan["sources"]), "queries": len(plan["queries"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
