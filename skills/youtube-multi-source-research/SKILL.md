---
name: youtube-multi-source-research
description: "Research a topic, question, one or more URLs, or an existing transcript across every relevant configured platform, including multiple YouTube videos, X, Reddit, Web, GitHub, Hacker News, RSS, and optional sources. Extract and compare transcripts, claims, reactions, and first-hand experiences into a cited cross-source brief. Use when the user says research, investigate, fact-check, compare, summarize the discussion, or asks to search all platforms."
---

# Universal Multi-Source Research

Use this Skill as a read-only, topic-first research orchestrator. The input may be a question, a topic, one URL, many URLs, or a transcript/document. Automatically choose every relevant configured source, include ordinary Web search and source-page reading, collect multiple independent YouTube videos when YouTube is relevant, compare claims and first-hand reports, and return a cited brief with coverage and uncertainty visible.

The package slug remains `youtube-multi-source-research` for backwards compatibility. Its behavior is universal rather than YouTube-only.

## Default research depth

Unless the user narrows the scope, make these four layers mandatory:

1. **Multiple YouTube videos:** target 5–10 usable, non-duplicate videos; prefer different channels and include official/primary, specialist, independent experience, recent update, and counterpoint perspectives when available.
2. **Ordinary Web search:** search and open official sites, primary documentation, news, blogs, Q&A, and source pages; do not rely only on a cross-source aggregator or search snippets.
3. **Community and implementation evidence:** inspect GitHub Issues and Discussions, repository/release context, Reddit submissions and comments, parent/reply context, and linked sources when the topic is relevant.
4. **Query diversity:** run Japanese and English variants, synonyms/related terms, exact-entity queries, implementation/experience queries, and criticism/limitation/counterargument queries. Keep the query families in the research plan.

If a platform or adapter is unavailable, record its status and continue; never reduce the target count silently or call unavailable coverage `no_results`.

## First-run setup and user guidance

Before a live external research run, check the available acquisition runtime when it is installed:

```bash
agent-reach doctor --json
```

If a required command or source is missing, tell the user in this form before continuing:

> Universal Multi-Source Research is installed and ready, but the following source(s) need local setup: `<sources>`. You can still use the available sources now. After local setup, start a new Codex task and run the same request again.

Use the source status from the diagnostic output. Do not ask the user to paste cookies, API keys, OAuth tokens, or passwords into chat. Do not configure authenticated sources automatically. Continue with public/read-only sources and report `auth_required`, `blocked`, or `not_configured` precisely.

## Operating contract

- Treat “調査して”, “リサーチして”, “全媒体で”, “比較して”, and equivalent requests as permission to search all relevant configured sources without requiring the user to name each platform.
- Default to read-only. Do not post, reply, vote, follow, subscribe, purchase, upload, or modify external content.
- Never put API keys, OAuth secrets, passwords, cookies, or bearer tokens into transcripts, evidence JSON, reports, prompts, commits, or logs.
- Preserve seed URLs, query plans, retrieval times, original source links, transcript type, timestamps, and source status.
- Separate verified facts, a source author's opinion or experience, maintainer/official claims, and the model's inference.
- Report each source as `complete`, `partial`, `auth_required`, `blocked`, `no_results`, `not_configured`, or `error`. Never describe a skipped or blocked source as evidence that no discussion exists.
- Engagement is a relevance signal, not proof of truth. Search ranking is not evidence quality.
- Do not claim to search “the entire internet.” Say which configured sources were searched, which were unavailable, and what the coverage window was.

## Input modes

### Topic or question only

When the user gives no URL, infer the entities, products, people, dates, handles, subreddits, repositories, and disputed terms in the question. Create the mandatory query families from the default research depth: original wording, Japanese, English, synonyms/related terms, exact names, official/primary source, news, implementation/tutorial, experience/review, criticism/limitations, and counterargument/alternative view. Route the plan to YouTube, X, Reddit, ordinary Web search and page reading, GitHub, Hacker News, and RSS by default; add configured optional sources such as TikTok, Instagram, Bluesky, LinkedIn, arXiv, Polymarket, Bilibili, or Xiaohongshu when they are relevant and available.

When YouTube is relevant, search for multiple candidate videos rather than selecting the first result. Prefer a diverse set: independent creators, official/primary channels, specialist explainers, recent updates, and credible counterpoints. Deduplicate near-identical reposts and cap the set using the source health, relevance, date, and diversity available in the active adapter. A normal default is 5–10 videos, with fewer only when the topic is narrow or the source returns fewer usable results.

### One or more URLs

Run `scripts/plan_research.py` first. A single X post, X thread, Reddit post, Reddit comment permalink, subreddit URL, or a mixture of these and other URLs is a valid input. Classify each URL and expand it into related evidence:

| Seed URL | Required expansion |
| --- | --- |
| YouTube video/channel/playlist | transcript or captions, video metadata, comments when available, 5–10 related non-duplicate videos when available, then X/Reddit/Web/GitHub corroboration |
| X post/thread/profile | post/thread text, replies, quoted posts, linked URLs, author context when available, then Reddit/YouTube/ordinary Web/GitHub corroboration |
| Reddit post/comment/subreddit/user | post/comment context, parent and replies when available, linked URLs, related discussions, then X/YouTube/ordinary Web/GitHub corroboration |
| GitHub repository/issue/discussion/release | README, releases, Issues, Discussions, maintainers, related repositories, then X/Reddit/YouTube/Web corroboration |
| Generic Web page, article, or PDF | page metadata and primary links, cited claims, then X/Reddit/YouTube/GitHub corroboration |
| Multiple mixed URLs | inspect each seed, deduplicate URLs and claims, cluster shared entities, and compare source agreement and disagreement |

If a YouTube URL is provided, it is a seed—not a limit of one video. Always attempt to find and compare related videos unless the user explicitly asks for that one video only. If a URL cannot be opened, retain it as a failed seed and continue with queries derived from its visible URL/title.

### Existing transcript or document

Normalize the supplied file with `scripts/extract_transcript.py --input`. Do not download the referenced video again. Preserve its timestamps and use the extracted claims as one evidence stream to fact-check across all relevant platforms.

## Workflow

### 1. Build the research plan

Create a working packet containing:

- the user's question and desired output;
- all seed URLs and their classifications;
- the recency window, normally 30 days for discussion/reaction research unless the user requests another period;
- language variants, normally Japanese and English when relevant;
- query families: exact, Japanese, English, synonym/related, official/primary, news, implementation, experience, criticism/limitations, and counterargument;
- source list, collection targets, expected result count, and source status;
- whether the user wants facts, opinions, reactions, implementation evidence, market sentiment, or first-hand experiences.

Use the deterministic planner:

```bash
python3 scripts/plan_research.py \
  --question "ユーザーの質問" \
  "https://example.com/seed" \
  --out work/research-plan.json
```

Read [references/source-routing.md](references/source-routing.md) to adjust source selection and YouTube diversity for the topic. Do not silently omit a source because it is harder to access; mark its status and continue with the available sources.

### 2. Check source health and select adapters

Use the current installed contracts rather than inventing undocumented command syntax. These are internal acquisition routes for this Skill; the user should invoke this Skill once rather than manually combining separate tools:

| Layer | Preferred tool | Role |
| --- | --- | --- |
| Access and routing | Agent-Reach | YouTube subtitles/transcription, public GitHub, Web, and configured X/Reddit routes; run `agent-reach doctor` when available |
| Cross-source discovery and synthesis | last30days-skill | Recent discovery, engagement-aware ranking, cross-source clusters, and cited synthesis across its supported platforms |
| Reddit precision | PRAW | Repeatable read-only submissions/comments, scores, timestamps, subreddit filters, and exact API collection |
| YouTube fallback | `yt-dlp` plus bundled normalizer | Multiple candidate video metadata/captions when the active access layer exposes them |

Agent-Reach is an access layer, not proof that a source is complete. last30days-skill is a discovery/synthesis layer, not a substitute for opening primary URLs. PRAW is only for Reddit and never posts. Follow each installed upstream Skill's current `SKILL.md` and report unavailable routes.

### 3. Collect multiple YouTube videos when relevant

For a topic or claim, run distinct searches for the main wording, exact entity, recent update, explanation/tutorial, independent experience, and counterpoint. Select several non-duplicate videos across channels and perspectives. For each selected video, preserve:

- video URL, title, channel, published date, and duration when available;
- transcript source (`manual`, `generated`, or `asr`), language, and retrieval method;
- timestamped transcript and material claims;
- comments/reactions only when the active adapter exposes them;
- whether the video is primary reporting, official material, commentary, tutorial, review, or repost.

For each video URL, use the bundled helper:

```bash
python3 scripts/extract_transcript.py \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --out work/youtube/VIDEO_ID --lang ja en
```

The URL helper tries `agent-reach transcribe`, then `yt-dlp` subtitles. Audio download plus `faster-whisper` requires an explicit `--allow-audio` decision. Never silently download audio. Run the helper separately for each selected video and keep one manifest per video.

### 4. Normalize and compare transcripts

Chunk each transcript without silently truncating either end:

```bash
python3 scripts/chunk_transcript.py \
  work/youtube/VIDEO_ID/transcript.json \
  --out work/youtube/VIDEO_ID/chunks.json \
  --max-chars 12000
```

Extract stable claim identifiers such as `claim-001` across all videos and non-video sources. For every material claim, record the source video ID or URL, quote, timestamp, claim type, search queries, and whether another independent source agrees, disagrees, or merely repeats it. Do not count duplicated clips, syndication, or many comments repeating the same assertion as independent corroboration.

When multiple videos cover the same claim, compare:

1. whether the wording and number are actually the same;
2. whether the videos cite a primary source or each other;
3. publication dates and updates;
4. creator expertise/role and disclosed conflicts;
5. independent agreement, disagreement, missing context, and first-hand evidence;
6. transcript confidence and timestamp links.

### 5. Search and collect every relevant configured platform

Use every query family in the plan, claim-specific and entity-specific, rather than one giant transcript query. Search the default set in parallel where the active tools allow it: YouTube, X, Reddit, Web, GitHub, Hacker News, and RSS. Add relevant optional sources from the plan. Do not skip the Japanese, English, synonym, or counterargument families merely because the first query returned results.

Use ordinary Web search for broad discovery, official documentation, news, blogs, Q&A, and primary pages. For GitHub, inspect Issues and Discussions rather than only the README. For Reddit, inspect comments and parent/reply context rather than only post titles. Use last30days-skill for recent cross-source discovery according to its current contract. Use Agent-Reach or the configured official/API adapter for retrieval. Use PRAW when Reddit comments, scores, timestamps, or subreddit filtering need precise repeatability. Open and preserve primary URLs for important claims; a search snippet alone is not equivalent to a source.

Keep first-hand experiences separate from official documentation, maintainer claims, and commentary. Record author, date, platform, direct URL, quoted passage, engagement context, and retrieval method without exposing credentials.

### 6. Normalize the evidence ledger

Convert adapter outputs to [references/evidence-schema.md](references/evidence-schema.md):

```bash
python3 scripts/normalize_evidence.py \
  --input work/raw-evidence.jsonl \
  --output work/evidence.jsonl
```

At minimum preserve `source`, `url`, `published_at`, `retrieved_at`, `author`, `title`, `text`, `quote`, `engagement`, `claim_ids`, `retrieval_method`, `source_role`, and `confidence`. Keep source status and error details in the ledger; do not turn an auth failure into `no_results`.

### 7. Write the final brief

Use [references/report-template.md](references/report-template.md) and report:

1. direct answer and confidence;
2. what was searched: question, URLs, date window, languages, platforms, and number of usable YouTube videos;
3. source coverage and blocked/not-configured routes;
4. claim-by-claim findings with timestamped video links where applicable;
5. agreement, disagreement, and source-dependency across the multiple videos and other platforms;
6. first-hand experiences, official/maintainer statements, and commentary as separate categories;
7. practical implications and remaining uncertainty;
8. direct source links with retrieval dates.

Say `not corroborated in the searched window` when a claim lacks independent support. Say `the selected sources agree` rather than presenting repeated or copied content as universal truth.

## Failure handling

- If subtitles are absent for one video, continue with the other selected videos and offer explicit opt-in ASR for that video.
- If a source is not configured, blocked, login-required, rate-limited, or schema-drifted, preserve that status and continue with the other sources.
- If YouTube returns too few distinct videos, report the actual count and do not imply full multi-video coverage.
- If only one video is usable, explicitly downgrade confidence and identify the missing diversity.
- If a URL is inaccessible, use its host/path/title tokens for discovery but label the seed as inaccessible.
- If a claim depends on an exact quote, retain the timestamp and link to the original video or post.
- If the user asks for more depth, expand the date window, query variants, and source count before writing a stronger conclusion.

## References

- Read [references/source-routing.md](references/source-routing.md) for topic/URL routing, platform expansion, and multi-video selection.
- Read [references/upstream-mapping.md](references/upstream-mapping.md) when choosing Agent-Reach, last30days-skill, and PRAW.
- Read [references/evidence-schema.md](references/evidence-schema.md) before writing or validating source records.
- Read [references/report-template.md](references/report-template.md) when producing a user-facing brief.
- Use the upstream projects' current documentation: [Agent-Reach](https://github.com/Panniantong/Agent-Reach), [last30days-skill](https://github.com/mvanhorn/last30days-skill), and [PRAW](https://github.com/praw-dev/praw).
