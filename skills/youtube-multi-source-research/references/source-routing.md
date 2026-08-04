# Source routing and multi-video policy

This reference defines the default orchestration policy. It is a routing contract, not a promise that every platform is configured or reachable in a particular environment.

## Default source set

For a normal topic/question, plan these sources unless the user narrows scope:

`youtube`, `x`, `reddit`, `web`, `github`, `hacker_news`, and `rss`.

Here `web` explicitly includes ordinary search-engine discovery plus opening the resulting official pages, articles, documentation, news, blogs, Q&A, and primary sources. It is not limited to the special cross-source skill.

The default depth is mandatory: target 5–10 diverse YouTube videos, perform ordinary Web search, inspect Reddit comments and GitHub Issues/Discussions, and run Japanese, English, synonym/related-term, experience, criticism, and counterargument query families. Lower the target only when the source returns fewer usable items and report the shortfall.

Standard and Deep plans include the optional identities as candidate sources even when the wording does not say “all platforms”. They remain candidates, not retrieval proof; an unavailable candidate must remain visible as `not_configured`, `blocked`, or another applicable status. Quick remains limited to YouTube and Web unless a seed requires its own source and the bounded YouTube/Web corroboration.

The current optional candidates are `tiktok`, `instagram`, `bluesky`, `linkedin`, `arxiv`, `polymarket`, `bilibili`, `xiaohongshu`, `facebook`, `v2ex`, `xiaoyuzhou`, and `xueqiu`. Do not add a platform by guessing from an unknown host.

## Collection limits

Standard and Deep plans expose numeric `collection_limits` in addition to the qualitative `collection_targets`. Each entry has `target` (normal goal), `min` (minimum evidence floor), and `max` (retrieval cap). A shortfall is reported; a `planned` entry is never counted as retrieved evidence.

| Source family | Standard | Deep |
| --- | --- | --- |
| YouTube videos | target 5 / min 3 / max 10 | target 8 / min 5 / max 12 |
| X primary posts | 10 / 5 / 20 | 20 / 10 / 40 |
| X replies | 20 / 10 / 40 | 40 / 20 / 80 |
| X quoted posts | 5 / 2 / 10 | 10 / 5 / 20 |
| Reddit submissions | 5 / 3 / 10 | 10 / 5 / 20 |
| Reddit comments | 20 / 10 / 40 | 40 / 20 / 80 |
| GitHub repositories / Issues / Discussions / releases | 3 / 1 / 6; 6 / 2 / 12; 4 / 1 / 8; 2 / 0 / 4 | 6 / 2 / 12; 12 / 4 / 24; 8 / 2 / 16; 4 / 0 / 8 |
| Opened Web pages | 12 / 8 / 15 | 20 / 12 / 25 |
| Hacker News discussions / RSS items | 3 / 1 / 8; 6 / 2 / 12 | 6 / 2 / 12; 10 / 4 / 20 |
| Optional candidate items | 3 / 1 / 8 | 6 / 2 / 12 |

Counts are role-specific: X replies and quoted posts are not mixed into primary-post counts, Reddit comments retain parent/reply context, and Web counts opened deduplicated pages rather than search-result snippets.

## Canonical source contract

`scripts/source_contract.py` is the single source of truth for source IDs and host aliases. The core IDs are `youtube`, `x`, `reddit`, `web`, `github`, `hacker_news`, and `rss`; the optional IDs are the twelve candidates above. Explicit valid IDs are preserved during evidence normalization. Known aliases and subdomains map to those IDs, while an otherwise unknown HTTP(S) host falls back to `web`.

## URL classification and expansion

| Host or URL shape | Class | Expand into |
| --- | --- | --- |
| `youtube.com/watch`, `youtu.be`, YouTube channel/playlist | youtube | captions/transcript, metadata, comments when available, related videos, then cross-platform claim checks |
| `x.com`, `twitter.com` | x | post/thread text, replies, quoted/linked posts, author context, linked primary pages, then Reddit/YouTube/Web/GitHub |
| `reddit.com/r/...`, Reddit comment permalinks, `old.reddit.com`, `redd.it` | reddit | submission/comment context, parent/replies, subreddit context, linked pages, then X/YouTube/Web/GitHub |
| `github.com/...` | github | README, releases, issues, discussions, contributors, related repositories, then X/Reddit/YouTube/Web |
| `news.ycombinator.com`, `ycombinator.com` | hacker_news | discussion context and linked primary sources |
| `tiktok.com`, `instagram.com`, `bsky.app`, `linkedin.com`, `arxiv.org`, `polymarket.com`, `bilibili.com`, `b23.tv`, `xiaohongshu.com`, `xhslink.com`, `facebook.com`, `v2ex.com`, `xiaoyuzhoufm.com`, `xueqiu.com` | matching optional candidate | source-specific public evidence when the adapter supports it |
| all other HTTP(S) URLs | web | page/PDF, citations and primary links, then X/Reddit/YouTube/GitHub |

When multiple URLs are supplied, treat them as seeds for one graph. Normalize canonical URLs, deduplicate pages and repeated claims, and preserve each seed's role in the evidence ledger.

## Topic query expansion

Generate at least these query families when relevant:

1. exact topic/entity;
2. Japanese and English variants;
3. recent update, release, or event;
4. tutorial, implementation, review, or real-world experience;
5. criticism, failure, limitation, or counterargument;
6. exact number, quote, product name, person, repository, or date from the input;
7. source-specific forms such as `site:reddit.com`, `site:github.com`, or a known X handle when the adapter supports them.

Do not stop after the exact query. A useful default ledger has these required families: exact, Japanese, English, synonyms/related terms, official/primary, news/update, implementation/tutorial, experience/review, criticism/limitations, counterargument/alternative view, Reddit comments, and GitHub Issues/Discussions.

Do not search the complete transcript as one query. Search material claims, named entities, dates, and disputed phrases separately.

## YouTube selection policy

YouTube is a source family, not a single citation. When it is relevant:

- default target: 5–10 usable videos;
- minimum quality target: 3 distinct videos when the topic has enough coverage;
- prefer diversity across official/primary, specialist, independent experience, recent update, and counterpoint videos;
- prefer different channels and original reporting over reuploads or clips;
- preserve at least one primary/official source when one exists, but do not treat official material as neutral commentary;
- use title/description/transcript overlap to detect near-duplicates;
- rank with relevance, transcript availability, date fit, source role, channel diversity, and evidence quality;
- comments are supporting context and are not independent confirmation of the video claim;
- if fewer than 3 distinct usable videos are found, lower confidence and state the count.

For a supplied YouTube URL, always search related videos and the video's core claims unless the user says “この1本だけ” or equivalent. For a channel or playlist URL, sample multiple videos rather than treating the channel page as one source.

For Standard and Deep plans focused on YouTube (a YouTube seed or explicit YouTube wording), `source_balance` must require at least one non-YouTube corroboration source. The plan records this requirement; it does not claim that the source has already been retrieved.

## Source status

Use one of:

- `complete`: the planned operation returned usable evidence;
- `partial`: some items or fields were unavailable;
- `auth_required`: login/API credentials are required;
- `blocked`: rate limit, CAPTCHA, 403, robots, or platform restriction;
- `no_results`: the adapter ran successfully but found no usable result;
- `not_configured`: the adapter is absent or not enabled;
- `error`: unexpected adapter or parsing failure.

`no_results` is valid only after a successful source query. Never use it for a source that was skipped or blocked.
