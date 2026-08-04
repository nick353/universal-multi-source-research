"""Canonical source identities and URL-host aliases for the research skill."""

from __future__ import annotations

from urllib.parse import urlparse


CORE_SOURCES = (
    "youtube",
    "x",
    "reddit",
    "web",
    "github",
    "hacker_news",
    "rss",
)
OPTIONAL_SOURCES = (
    "tiktok",
    "instagram",
    "bluesky",
    "linkedin",
    "arxiv",
    "polymarket",
    "bilibili",
    "xiaohongshu",
    "facebook",
    "v2ex",
    "xiaoyuzhou",
    "xueqiu",
)
ALL_SOURCES = CORE_SOURCES + OPTIONAL_SOURCES

# ``other`` was accepted by the original evidence normalizer. Keep it valid
# for compatibility, while not treating it as a planned platform.
COMPATIBILITY_SOURCES = ("other",)
VALID_SOURCE_IDS = frozenset(ALL_SOURCES + COMPATIBILITY_SOURCES)

SOURCE_ALIASES = {
    "yt": "youtube",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "twitter": "x",
    "twitter/x": "x",
    "twitter.com": "x",
    "x.com": "x",
    "hn": "hacker_news",
    "hackernews": "hacker_news",
    "hacker-news": "hacker_news",
    "news.ycombinator.com": "hacker_news",
    "ycombinator": "hacker_news",
    "reddit.com": "reddit",
    "redd.it": "reddit",
    "old.reddit.com": "reddit",
    "github.com": "github",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "bsky.app": "bluesky",
    "linkedin.com": "linkedin",
    "arxiv.org": "arxiv",
    "polymarket.com": "polymarket",
    "bilibili.com": "bilibili",
    "b23.tv": "bilibili",
    "xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
    "facebook.com": "facebook",
    "v2ex.com": "v2ex",
    "xiaoyuzhoufm.com": "xiaoyuzhou",
    "xueqiu.com": "xueqiu",
}

HOST_ALIASES = {
    "youtube.com": "youtube",
    "youtube-nocookie.com": "youtube",
    "youtu.be": "youtube",
    "twitter.com": "x",
    "x.com": "x",
    "t.co": "x",
    "reddit.com": "reddit",
    "redd.it": "reddit",
    "github.com": "github",
    "news.ycombinator.com": "hacker_news",
    "ycombinator.com": "hacker_news",
    "tiktok.com": "tiktok",
    "instagram.com": "instagram",
    "bsky.app": "bluesky",
    "linkedin.com": "linkedin",
    "arxiv.org": "arxiv",
    "polymarket.com": "polymarket",
    "bilibili.com": "bilibili",
    "b23.tv": "bilibili",
    "xiaohongshu.com": "xiaohongshu",
    "xhslink.com": "xiaohongshu",
    "facebook.com": "facebook",
    "v2ex.com": "v2ex",
    "xiaoyuzhoufm.com": "xiaoyuzhou",
    "xueqiu.com": "xueqiu",
}


def _token(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def canonical_source(value: object) -> str | None:
    """Return a canonical source ID, or ``None`` for an unknown explicit value."""
    token = _token(value)
    if not token:
        return None
    token = SOURCE_ALIASES.get(token, token)
    return token if token in VALID_SOURCE_IDS else None


def source_for_host(host: object) -> str | None:
    """Map an exact host or subdomain to a configured source identity."""
    value = _token(host).split(":", 1)[0].rstrip(".")
    if not value:
        return None
    for alias, source in sorted(HOST_ALIASES.items(), key=lambda item: -len(item[0])):
        if value == alias or value.endswith("." + alias):
            return source
    return None


def source_from_url(url: object) -> str | None:
    """Map a URL host to a source; unknown HTTP(S) hosts remain ``web``."""
    value = str(url or "").strip()
    if not value:
        return None
    parsed = urlparse(value if "://" in value else "//" + value)
    return source_for_host(parsed.hostname) or ("web" if parsed.scheme in {"", "http", "https"} else None)
