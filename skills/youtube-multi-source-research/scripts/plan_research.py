#!/usr/bin/env python3
"""Create a deterministic cross-platform research plan from a question and URLs."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from source_contract import CORE_SOURCES, OPTIONAL_SOURCES, source_from_url

DEFAULT_SOURCES = list(CORE_SOURCES)
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
    "facebook": ["posts", "pages", "groups", "linked sources"],
    "v2ex": ["topics", "replies", "node context", "linked sources"],
    "xiaoyuzhou": ["podcast episodes", "transcripts", "show context", "linked sources"],
    "xueqiu": ["market data", "community posts", "replies", "linked sources"],
}

MODE_CONFIG = {
    "quick": {
        "sources": ["youtube", "x", "reddit", "web"],
        "youtube_target": 3,
        "youtube_maximum": 5,
        "youtube_minimum": 2,
        "query_family_ids": ["exact", "japanese", "official", "experience", "criticism", "reddit_comments"],
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


def limit_spec(target: int, minimum: int, maximum: int) -> dict[str, int]:
    """Describe a soft target, evidence floor, and per-source retrieval cap."""
    return {"target": target, "min": minimum, "max": maximum}


OPTIONAL_COLLECTION_LIMITS = {
    source: {"items": limit_spec(3, 1, 8)}
    for source in OPTIONAL_SOURCES
}

COLLECTION_LIMITS = {
    "quick": {
        "youtube": {"items": limit_spec(3, 2, 5)},
        "x": {
            "primary_posts": limit_spec(2, 2, 5),
            "replies": limit_spec(2, 0, 5),
            "quoted_posts": limit_spec(0, 0, 2),
        },
        "reddit": {
            "submissions": limit_spec(2, 2, 5),
            "comments": limit_spec(2, 0, 5),
        },
        "web": {"opened_pages": limit_spec(3, 1, 6)},
    },
    "standard": {
        "youtube": {"items": limit_spec(5, 3, 10)},
        "x": {
            "primary_posts": limit_spec(10, 5, 20),
            "replies": limit_spec(20, 10, 40),
            "quoted_posts": limit_spec(5, 2, 10),
        },
        "reddit": {
            "submissions": limit_spec(5, 3, 10),
            "comments": limit_spec(20, 10, 40),
        },
        "github": {
            "repositories": limit_spec(3, 1, 6),
            "issues": limit_spec(6, 2, 12),
            "discussions": limit_spec(4, 1, 8),
            "releases": limit_spec(2, 0, 4),
        },
        "web": {"opened_pages": limit_spec(12, 8, 15)},
        "hacker_news": {"discussions": limit_spec(3, 1, 8)},
        "rss": {"items": limit_spec(6, 2, 12)},
        **OPTIONAL_COLLECTION_LIMITS,
    },
    "deep": {
        "youtube": {"items": limit_spec(8, 5, 12)},
        "x": {
            "primary_posts": limit_spec(20, 10, 40),
            "replies": limit_spec(40, 20, 80),
            "quoted_posts": limit_spec(10, 5, 20),
        },
        "reddit": {
            "submissions": limit_spec(10, 5, 20),
            "comments": limit_spec(40, 20, 80),
        },
        "github": {
            "repositories": limit_spec(6, 2, 12),
            "issues": limit_spec(12, 4, 24),
            "discussions": limit_spec(8, 2, 16),
            "releases": limit_spec(4, 0, 8),
        },
        "web": {"opened_pages": limit_spec(20, 12, 25)},
        "hacker_news": {"discussions": limit_spec(6, 2, 12)},
        "rss": {"items": limit_spec(10, 4, 20)},
        **{
            source: {"items": limit_spec(6, 2, 12)}
            for source in OPTIONAL_SOURCES
        },
    },
}


def active_collection_limits(mode: str, sources: list[str]) -> dict[str, dict[str, dict[str, int]]]:
    """Return limits for every planned source, including bounded seed-only sources."""
    configured = COLLECTION_LIMITS[mode]
    return {
        source: configured.get(source, {"items": limit_spec(1, 1, 3)})
        for source in sources
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
    parsed = urlparse(value if "://" in value else "//" + value)
    path = (parsed.path or "").lower()
    source = source_from_url(value)
    if source == "web" and path.endswith(".pdf"):
        return "web_pdf"
    if source:
        return source
    return "web"


def source_expansion(seed_type: str, mode: str = "standard") -> list[str]:
    expansions = {
        "youtube": ["youtube", "x", "reddit", "web", "github"],
        "x": ["x", "reddit", "youtube", "web", "github"],
        "reddit": ["reddit", "x", "youtube", "web", "github"],
        "github": ["github", "x", "reddit", "youtube", "web"],
        "web": ["web", "x", "reddit", "youtube", "github"],
        "web_pdf": ["web", "x", "reddit", "youtube", "github"],
    }
    quick_expansions = {
        "youtube": ["youtube", "x", "reddit", "web"],
        "x": ["x", "reddit", "web", "youtube"],
        "reddit": ["reddit", "x", "web", "youtube"],
        "github": ["github", "x", "reddit", "web", "youtube"],
        "web": ["web", "x", "reddit", "youtube"],
        "web_pdf": ["web", "x", "reddit", "youtube"],
    }
    if mode == "quick":
        if seed_type in OPTIONAL_SOURCES:
            return [seed_type, "x", "reddit", "web", "youtube"]
        return quick_expansions.get(seed_type, ["web", "x", "reddit", "youtube"])
    if seed_type in OPTIONAL_SOURCES:
        return [seed_type, "x", "reddit", "youtube", "web", "github"]
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
        for source in source_expansion(seed["type"], mode):
            if source not in sources:
                sources.append(source)
    optional_candidates = []
    if mode in {"standard", "deep"}:
        sources.extend(source for source in OPTIONAL_SOURCES if source not in sources)
        optional_candidates = [source for source in OPTIONAL_SOURCES if source in sources]
    source_roles = {
        source: "core" if source in CORE_SOURCES else "optional_candidate"
        for source in sources
    }
    collection_limits = active_collection_limits(mode, sources)
    youtube_focused = bool(
        any(seed["type"] == "youtube" for seed in seeds)
        or re.search(r"youtube|ユーチューブ", question, re.I)
    )
    non_youtube_sources = [source for source in sources if source != "youtube"]
    corroboration_required = youtube_focused
    source_records = [
        {
            "source": source,
            "status": "planned",
            "selection_role": source_roles[source],
            "collection_limits": collection_limits[source],
            "retrieval_role": {
                "web": "ordinary web search plus opening official pages, news, blogs, Q&A, and primary sources",
                "youtube": "multiple diverse videos, captions/transcripts, metadata, and related claims",
                "x": "posts, threads, replies, quotes, and linked sources",
                "reddit": "submissions, comments, subreddit context, and linked sources",
                "github": "repositories, releases, issues, discussions, and maintainers",
                "hacker_news": "technical discussions and linked primary sources",
                "rss": "recent feeds and source discovery",
                "facebook": "posts, pages, groups, and linked sources",
                "v2ex": "topics, replies, node context, and linked sources",
                "xiaoyuzhou": "podcast episodes, transcripts, and linked sources",
                "xueqiu": "market data, community posts, replies, and linked sources",
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
        "collection_limits": collection_limits,
        "mode": mode,
        "mode_selection": {
            "requested": requested_mode,
            "selected": mode,
            "automatic": requested_mode == "auto",
            "reason": mode_reason,
        },
        "source_selection": {
            "core_sources": list(CORE_SOURCES),
            "optional_candidates": optional_candidates,
            "optional_candidates_included_by_default": mode in {"standard", "deep"},
            "all_platform_wording_required": False,
            "seed_expansion": "mode-bounded; X and Reddit remain required community sources in every mode",
        },
        "source_balance": {
            "core_source_count": len([source for source in sources if source in CORE_SOURCES]),
            "optional_candidate_count": len(optional_candidates),
            "youtube_focused": youtube_focused,
            "non_youtube_corroboration_required": corroboration_required,
            "minimum_non_youtube_corroboration": 1 if corroboration_required else 0,
            "non_youtube_sources": non_youtube_sources,
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
            "required_sources": ["x", "reddit"],
            "live_gate_required_in_every_mode": True,
            "minimum_relevant_body_records_per_source": 2,
            "reddit_comments_required": True,
            "github_issues_required": True,
            "github_discussions_required": True,
        },
        "principles": [
            "A blocked or unconfigured source is not no_results.",
            "Every non-narrowed run must pass the X/Reddit live retrieval gate before collection or report saving.",
            "A plan or source-health result is never retrieval evidence.",
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
