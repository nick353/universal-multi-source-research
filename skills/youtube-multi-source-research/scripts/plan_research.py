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
MODE_NAMES = ("quick", "standard", "deep")
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

MODE_CONFIG = {
    "quick": {
        "sources": ["youtube", "web"],
        "youtube_target": 3,
        "youtube_maximum": 5,
        "youtube_minimum": 2,
        "query_family_ids": ["exact", "japanese", "official", "experience", "criticism"],
        "label": "簡易調査",
    },
    "standard": {
        "sources": DEFAULT_SOURCES,
        "youtube_target": 5,
        "youtube_maximum": 10,
        "youtube_minimum": 3,
        "query_family_ids": [family["id"] for family in QUERY_FAMILIES],
        "label": "標準調査",
    },
    "deep": {
        "sources": DEFAULT_SOURCES,
        "youtube_target": 8,
        "youtube_maximum": 12,
        "youtube_minimum": 5,
        "query_family_ids": [family["id"] for family in QUERY_FAMILIES],
        "label": "深掘り調査",
    },
}


def select_research_mode(question: str, urls: list[str], requested_mode: str = "auto") -> tuple[str, str]:
    """Select a workload automatically without asking the user to choose a mode."""
    if requested_mode in MODE_NAMES:
        return requested_mode, "明示された内部モード指定"

    text = question.strip()
    lowered = text.lower()
    broad = bool(re.search(r"全プラットフォーム|全媒体|すべて|全部|万能|横断|every platform|all platforms", text, re.I))
    deep_terms = bool(re.search(
        r"最新|比較|徹底|深掘り|詳しく|評判|口コミ|実体験|反対意見|問題点|批判|台本|市場|競合|複数|レビュー|失敗|導入|コスト|最新|latest|compare|deep|review|script",
        lowered,
        re.I,
    ))
    quick_terms = bool(re.search(r"要点だけ|簡単に|ざっくり|短く|一言|とは何|何ですか|quick|brief|short|what is", lowered, re.I))
    single_only = bool(re.search(r"1本だけ|この動画だけ|single video|only this video", lowered, re.I))

    if broad or deep_terms or len(urls) >= 2 or len(text) >= 100:
        return "deep", "複数媒体・比較・最新性・実体験など、検証量が必要な依頼"
    if quick_terms or single_only:
        return "quick", "短い確認、定義、要点整理、または単一動画に限定された依頼"
    return "standard", "通常のテーマ調査として、主要媒体を横断する既定"


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


def make_queries(question: str, urls: list[str], families: list[dict]) -> list[str]:
    queries: list[str] = []
    base = question.strip()
    if base:
        for family in families:
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


def query_family_plan(families: list[dict]) -> list[dict]:
    return [
        {
            "id": family["id"],
            "label": family["label"],
            "required": family["required"],
            "agent_action": "Generate a natural-language Japanese/English variant or synonym rather than blindly appending the label." if family["id"] in {"japanese", "english", "synonyms"} else "Run this family against the relevant sources and preserve the results separately.",
        }
        for family in families
    ]


def build_plan(question: str, urls: list[str], window_days: int, requested_mode: str = "auto") -> dict:
    mode, mode_reason = select_research_mode(question, urls, requested_mode)
    mode_config = MODE_CONFIG[mode]
    families = [family for family in QUERY_FAMILIES if family["id"] in mode_config["query_family_ids"]]
    seeds = [{"url": url, "type": classify_url(url)} for url in urls]
    sources = list(mode_config["sources"])
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
            "collection_targets": (
                [
                    f"{mode_config['youtube_target']}-{mode_config['youtube_maximum']} diverse videos",
                    "captions or transcripts",
                    "metadata",
                    "related claims",
                ]
                if source == "youtube"
                else SOURCE_TARGETS.get(source, ["relevant configured platform search and source retrieval"])
            ),
            "youtube_video_target": (
                f"{mode_config['youtube_target']}-{mode_config['youtube_maximum']} diverse videos"
                if source == "youtube" else None
            ),
        }
        for source in sources
    ]
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "window_days": window_days,
        "seeds": seeds,
        "queries": make_queries(question, urls, families),
        "query_families": query_family_plan(families),
        "sources": source_records,
        "mode": mode,
        "mode_selection": {
            "requested": requested_mode,
            "selected": mode,
            "automatic": requested_mode == "auto",
            "reason": mode_reason,
        },
        "youtube_policy": {
            "target_count": mode_config["youtube_target"],
            "maximum_count": mode_config["youtube_maximum"],
            "minimum_distinct_count": mode_config["youtube_minimum"],
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
            "The final answer must start with the source coverage block before the conclusion.",
            "Save the completed report through save_report.py in the stable report directory.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="Seed URLs")
    parser.add_argument("--question", default="", help="Research question or topic")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--mode", choices=["auto", *MODE_NAMES], default="auto", help="Research mode; auto is the default")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()
    plan = build_plan(args.question, args.urls, args.window_days, args.mode)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(output), "sources": len(plan["sources"]), "queries": len(plan["queries"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
