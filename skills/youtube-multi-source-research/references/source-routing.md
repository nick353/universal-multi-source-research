# Source routing and multi-video policy

This reference defines the default orchestration policy. It is a routing contract, not a promise that every platform is configured or reachable in a particular environment.

## Default source set

For a normal topic/question, plan these sources unless the user narrows scope:

`youtube`, `x`, `reddit`, `web`, `github`, `hacker_news`, and `rss`.

Here `web` explicitly includes ordinary search-engine discovery plus opening the resulting official pages, articles, documentation, news, blogs, Q&A, and primary sources. It is not limited to the special cross-source skill.

The default depth is mandatory: target 5–10 diverse YouTube videos, perform ordinary Web search, inspect Reddit comments and GitHub Issues/Discussions, and run Japanese, English, synonym/related-term, experience, criticism, and counterargument query families. Lower the target only when the source returns fewer usable items and report the shortfall.

Add `tiktok`, `instagram`, `bluesky`, `linkedin`, `arxiv`, `polymarket`, `bilibili`, or `xiaohongshu` only when the topic is relevant and the active adapter supports the source. A source that is not configured must remain visible as `not_configured`.

## URL classification and expansion

| Host or URL shape | Class | Expand into |
| --- | --- | --- |
| `youtube.com/watch`, `youtu.be`, YouTube channel/playlist | youtube | captions/transcript, metadata, comments when available, related videos, then cross-platform claim checks |
| `x.com`, `twitter.com` | x | post/thread text, replies, quoted/linked posts, author context, linked primary pages, then Reddit/YouTube/Web/GitHub |
| `reddit.com/r/...`, Reddit comment permalinks, `old.reddit.com`, `redd.it` | reddit | submission/comment context, parent/replies, subreddit context, linked pages, then X/YouTube/Web/GitHub |
| `github.com/...` | github | README, releases, issues, discussions, contributors, related repositories, then X/Reddit/YouTube/Web |
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
