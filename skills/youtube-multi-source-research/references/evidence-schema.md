# Evidence schema

Store one JSON object per line in `evidence.jsonl`. Do not store cookies, tokens, authorization headers, or raw environment dumps.

## Required shape

```json
{
  "source": "youtube",
  "url": "https://example.com/source",
  "retrieved_at": "2026-07-29T00:00:00Z",
  "published_at": "2026-07-28T00:00:00Z",
  "author": "source author or null",
  "title": "source title or null",
  "text": "normalized source text",
  "quote": "short supporting excerpt or null",
  "engagement": {
    "score": 42,
    "comments": 7,
    "likes": null,
    "views": null,
    "reposts": null
  },
  "claim_ids": ["claim-001"],
  "retrieval_method": "official_api",
  "confidence": "high",
  "status": "complete"
}
```

## Allowed values

### `source`

Canonical IDs are `youtube`, `x`, `reddit`, `web`, `github`, `hacker_news`, `rss`, `tiktok`, `instagram`, `bluesky`, `linkedin`, `arxiv`, `polymarket`, `bilibili`, `xiaohongshu`, `facebook`, `v2ex`, `xiaoyuzhou`, and `xueqiu`. The legacy compatibility value `other` is preserved when explicitly supplied. Known host aliases are normalized by `scripts/source_contract.py`; unknown HTTP(S) hosts fall back to `web`.

### `retrieval_method`

Use the most specific method available:

- `official_api`
- `praw`
- `agent_reach`
- `authenticated_browser`
- `yt_dlp`
- `youtube_transcript_api`
- `asr`
- `rss`
- `search_snippet`
- `manual`

### `confidence`

- `high`: direct official/primary source or exact API object with stable URL;
- `medium`: direct public post, transcript, or maintainer artifact with some extraction risk;
- `low`: search snippet, indirect summary, or fragile scrape.

### `status`

`complete`, `partial`, `auth_required`, `blocked`, `no_results`, `not_configured`, or `error`.

## Evidence rules

- `text` is the normalized body, not an AI paraphrase.
- `quote` should be short and traceable to `text`; never create a quote from a model summary.
- `claim_ids` links evidence to the transcript claim ledger.
- `engagement` is optional and must preserve the platform's meaning. Do not compare a Reddit score and an X like count as if they were the same metric.
- `retrieved_at` is required even when `published_at` is unknown.
- If a source failed, write a source-status record rather than an empty evidence record.

For source-status packets, YouTube uses separate `count` (candidate videos) and `usable_count` (videos with usable transcript/metadata evidence). `usable_count` is mandatory when YouTube is required; candidate URLs alone do not satisfy retrieval.

## Common runner metadata

For an ordinary non-narrowed run, create the packet with `scripts/research_runner.py start` and keep these fields unchanged across plan, status, validation, coverage, and saved report audit files:

- `contract_version`: `universal_research_run.v1`
- `run_id`: one stable identifier for the entire run
- `research_mode` / `mode`: `quick`, `standard`, or `deep`
- `required_sources`: `["youtube", "x", "reddit", "web"]`
- `source_order`: the same four IDs in that order
- `query_families_required` and `query_families_executed`

Use `record` only after the adapter has returned a terminal source result. It may preserve `complete`, `partial`, `auth_required`, `blocked`, `no_results`, `not_configured`, or `error`, but it must not turn a planned source into success. `finalize` is the only common-runner completion decision; it requires source-native evidence and the selected mode's minimum counts.
