---
name: youtube-multi-source-research
description: "Top-level automatic research entry for a topic, question, one or more URLs, or an existing transcript. Research across every relevant configured platform, including multiple YouTube videos, X, Reddit, Web, GitHub, Hacker News, RSS, and optional sources. Perform live read-only retrieval, preserve source-native URLs, validate evidence before claiming completion, and extract and compare transcripts, claims, reactions, and first-hand experiences into a cited cross-source brief. Invoke automatically without requiring the user to name a skill when the user asks to リサーチして、調査して、調べて、検索して、探して、比較して、検証して、評判・口コミ・体験談・問題点・最新情報を調べる, or equivalent research in English. Explicit media limits and purely local file/code inspection take precedence; do not use when browsing is explicitly excluded."
---

# Universal Multi-Source Research

Use this Skill as a read-only, topic-first research orchestrator. The input may be a question, a topic, one URL, many URLs, or a transcript/document. Automatically choose the research depth and every relevant configured source, include ordinary Web search and source-page reading, collect multiple independent YouTube videos when YouTube is relevant, compare claims and first-hand reports, save the completed brief to the stable report directory, and return a cited brief with coverage and uncertainty visible.

The package slug remains `youtube-multi-source-research` for backwards compatibility. Its behavior is universal rather than YouTube-only.

## Top-level automatic entry

For an unqualified external request such as “リサーチして”, “調査して”, or “調べて”, select this Skill before choosing an acquisition adapter. The user does not need to mention the Skill name or list the platforms. Keep explicit media limits, a single-video-only request, and a no-browsing instruction authoritative.

For an ordinary unqualified run, the completion contract is the four-source core: YouTube, X, Reddit, and ordinary Web. Internal adapters such as Agent-Reach or last30days-skill may collect or rank evidence, but they never replace a core-source execution or its source-native evidence.

## Default research depth

Unless the user explicitly narrows the scope to particular media, make these four media mandatory on every ordinary research run:

1. **Multiple YouTube videos:** target 5–10 usable, non-duplicate videos; prefer different channels and include official/primary, specialist, independent experience, recent update, and counterpoint perspectives when available.
2. **Ordinary Web search:** search and open official sites, primary documentation, news, blogs, Q&A, and source pages; do not rely only on a cross-source aggregator or search snippets.
3. **Community evidence:** inspect X posts/threads and replies, Reddit submissions/comments and parent/reply context. GitHub Issues and Discussions, repository/release context, and linked sources are additional implementation evidence when relevant.
4. **Query diversity:** run Japanese and English variants, synonyms/related terms, exact-entity queries, implementation/experience queries, and criticism/limitation/counterargument queries. Keep the query families in the research plan.

If a required platform or adapter is unavailable, record the exact status and continue collecting only for a clearly partial run. Never reduce the target count silently, call unavailable coverage `no_results`, or return/save that run as `complete`.

## Automatic research mode

Do not ask the user to choose a mode. Run `scripts/plan_research.py` with its default `--mode auto` and use the selected mode in the plan and report.

- **Quick**: short factual checks, definitions, “要点だけ”, or an explicitly single-video request. Target 3–5 YouTube videos and a smaller query set, but still run the bounded X/Reddit live gate and collect the minimum community evidence floor.
- **Standard**: the default for a normal topic or URL investigation. Search the core configured set, include the optional sources as candidates, and target 5–10 diverse YouTube videos.
- **Deep**: automatically choose for comparisons, multiple URLs, “最新/評判/実体験/問題点/台本/徹底”, broad cross-platform requests, or long/complex questions. Target 8–12 YouTube videos, include optional sources as candidates, and keep all core query families.

Quick remains bounded by smaller collection limits, but the non-narrowed completion set is still exactly YouTube, X, Reddit, and ordinary Web. Standard and Deep record `source_selection` and `source_balance`; when focused on YouTube they require non-YouTube corroboration. A `planned` source is only a plan entry and must never be reported as retrieved evidence.

Standard and Deep also record source-specific `collection_limits` with `target`, `min`, and `max` values. X is counted separately as primary posts, replies, and quoted posts; Reddit separates submissions and comments; GitHub separates repositories, Issues, Discussions, and releases; Web counts opened deduplicated pages. Report shortfalls instead of silently accepting a smaller sample.

Source selection remains automatic inside the selected mode. A seed URL always forces its own platform and required corroboration sources into the plan. If the user explicitly requests a mode, honor it; otherwise never expose a mode-selection question.

## Report display contract

Write the final brief in Japanese unless the user requests another language. Optimize the first screen for a decision, not for dumping the evidence:

1. source coverage and automatic mode;
2. a short “あなた向けの判断” section;
3. a 1-minute summary;
4. a compact comparison table;
5. YouTube transcript/index and script-ready points;
6. separate official facts, X/Reddit first-hand reports, GitHub issues, ordinary Web evidence, counterpoints, and limitations;
7. detailed claims and source links.

Keep comparison-table cells short. Move long explanations to the sections below. Always distinguish a direct capture from a downstream researcher report and a source author's opinion from a verified fact.

## System language

Keep system and operational messages in English, including setup instructions, health checks, authentication state, success messages (`Login successful.`), failure messages, and saved-report confirmations. Preserve stable status codes and source IDs exactly as received from adapters.

Keep the research brief in Japanese by default unless the user requests English. Do not expose upstream Agent-Reach locale text in the final answer.

## First-run setup and user guidance

Before a live external research run, check the available acquisition runtime when it is installed. Use the bundled English adapter so upstream locale text is not shown:

```bash
python3 scripts/agent_reach_status.py --json
```

The adapter calls `agent-reach doctor --json`, preserves machine-readable status fields, and translates only the display boundary. Do not modify the installed Agent-Reach package to change its hard-coded messages; package updates would overwrite that change.

If a required command or source is missing, tell the user in this form before continuing:

> Universal Multi-Source Research is installed and ready, but the following source(s) need local setup: `<sources>`. You can still use the available sources now. After local setup, start a new Codex task and run the same request again.

Use the source status from the diagnostic output. Do not ask the user to paste cookies, API keys, OAuth tokens, or passwords into chat. Do not configure authenticated sources automatically. Continue with public/read-only sources and report `auth_required`, `blocked`, or `not_configured` precisely.

## Operating contract

- Treat “調査して”, “リサーチして”, “全媒体で”, “比較して”, and equivalent requests as permission to search all relevant configured sources without requiring the user to name each platform.
- Treat a normal public/read-only research request as execution authorization for source selection, public queries, opening public pages, retrieving public posts/video metadata/captions, local evidence validation, and report generation. Do not ask for approval per source, query, page, or normal retrieval tool; start automatically. This does not authorize login, private or paid data, secrets, posting or engagement, sending, purchasing, permissions, or destructive/irreversible changes.
- Do not treat `active_backend: null` alone as source unavailability. If the health check says an OpenCLI bridge is connected or explicit credentials are configured, classify the source as `configured_unverified`, run one documented read-only smoke command, and use it when that command succeeds. On failure, preserve the exact `auth_required`, `blocked`, or `error` status; never silently omit the source or call it `no_results`.
- Default to read-only. Do not post, reply, vote, follow, subscribe, purchase, upload, or modify external content.
- Never put API keys, OAuth secrets, passwords, cookies, or bearer tokens into transcripts, evidence JSON, reports, prompts, commits, or logs.
- Preserve seed URLs, query plans, retrieval times, original source links, transcript type, timestamps, and source status.
- Separate verified facts, a source author's opinion or experience, maintainer/official claims, and the model's inference.
- Report each source as `complete`, `partial`, `auth_required`, `blocked`, `no_results`, `not_configured`, or `error`. Never describe a skipped or blocked source as evidence that no discussion exists.
- Engagement is a relevance signal, not proof of truth. Search ranking is not evidence quality.
- Do not claim to search “the entire internet.” Say which configured sources were searched, which were unavailable, and what the coverage window was.

## Non-negotiable live retrieval gate

The plan, `agent-reach doctor`, a connector list, a search snippet, or a statement that a source is configured is not retrieval evidence. A research run is only complete after it has live source-native results and a source-status packet that passes validation.

For every non-narrowed research run, including Quick, run the bundled admission gate below before substantive collection. Use the same query family and the same configured backend for the actual X/Reddit collection:

```bash
python3 scripts/research_gate.py \
  --query "主要な調査語" \
  --out work/research-gate.json
```

The gate must return source-native URLs and pass `validate_research_evidence.py` for both X and Reddit. A ready gate is only an admission check: still open relevant posts/threads and Reddit submissions/comments, preserve their direct URLs, and record their retrieval method in the evidence ledger. If the gate fails, preserve the exact blocker and continue only as an explicitly `research_incomplete`/partial run; do not claim completed cross-platform coverage. The final four-media gate below remains mandatory even when this admission gate is ready.

The underlying read-only probe can also be run directly for diagnostics:

```bash
python3 scripts/live_source_probe.py \
  --source x --source reddit \
  --query "主要な調査語" \
  --out work/live-source-probe.json
```

The probe must return source-native URLs and a positive count for a source to be called `complete`. It is an admission check, not the final evidence: open relevant X posts/threads and Reddit submissions/comments, preserve their direct URLs, and record their retrieval method in the evidence ledger. Do not replace those steps with only the probe output.

The probe tries the configured OpenCLI adapter once and, only after a read-only failure, one installed platform-specific fallback (`twitter-cli` for X or `rdt-cli` for Reddit). For `twitter-cli`, it passes Agent-Reach's stored `auth_token`/`ct0` only through the child process environment; it never writes or logs those values. It records `configured`, `smoke_attempted`, `smoke_result`, `fallback_attempted`, and `evidence_retrieved` for each source. A fallback attempt is not a success claim; the source still needs native URLs and validator approval.

### YouTube candidate-versus-evidence gate

YouTube candidate search is discovery only. A result title, watch URL, channel, view count, or a list of five search hits never counts as usable YouTube evidence by itself. For every selected video, write a transcript/metadata record with the direct URL, retrieval method, transcript status (`full`, `partial`, or `unavailable`), and at least one body-bearing claim or verified metadata field. The source-status record must include both `count` (candidates) and an explicit `usable_count` (videos with usable transcript/metadata evidence), plus `evidence_urls` and the exact shortfall reason. Never infer `usable_count` from `count`.

日本語で言えば、YouTubeは「候補検索だけでは証拠にならない」という扱いです。

When YouTube is in any non-narrowed plan, the final four-media validator below checks `usable_count`. It fails when `usable_count` is absent or zero, even if candidate URLs exist. A partial YouTube source with a positive `usable_count` may be reported as partial, but it must preserve the missing-video reason and must not be described as full coverage.

### Topic and content relevance gate

Search results are candidates, not evidence. Search ranking, a matching title, or a single shared word is not enough. For every retained X/Reddit/Web/GitHub item, open the source record and capture its actual body/text (X `text`; Reddit search `selftext`; Reddit read `text`), direct URL, author/date, and the claim or experience it supports. Mark each candidate `topic_relevance` as `relevant`, `partial`, or `irrelevant` and add a short `relevance_reason`. Exclude `irrelevant` items from source counts and conclusions. Never create source content from a title or search snippet.

Normalize with topic metadata so the ledger makes the content check visible:

```bash
python3 scripts/normalize_evidence.py \
  --input work/raw-evidence.jsonl \
  --output work/evidence.jsonl \
  --topic "調査テーマ"
```

Then require at least two reviewed, body-bearing, relevant records per required community source:

```bash
python3 scripts/validate_topic_evidence.py \
  --input work/evidence.jsonl \
  --topic "調査テーマ" \
  --keyword "主要エンティティ" --keyword "主要な問題・機能" \
  --require-source x --require-source reddit \
  --min-relevant 2 \
  --out work/topic-validation.json
```

If this validator fails, label the result `research_incomplete` or `partial`; do not count noisy search hits as topic evidence. For Reddit, keep the search result URL when `reddit read` omits a URL from the returned comment/body records, and associate the opened body with that parent URL explicitly.

### Fixed four-media completion gate

For every ordinary run without an explicit media limitation, completion means the fixed set `[youtube, x, reddit, web]` has passed one final, fail-closed contract. Each record must prove all of the following: a dedicated runner was executed (`runner_executed: true`), it reached terminal success (`terminal_success: true`), evidence was actually retrieved (`evidence_retrieved: true`), the record has a non-empty `retrieval_method`, a positive evidence count, and valid source-native URLs. YouTube additionally requires a positive `usable_count` backed by transcript or verified metadata evidence. X and Reddit require body-bearing post/comment records. Web requires at least one body-bearing opened page; a Web search result, URL candidate, or a Web page mentioning another platform never fulfills that platform.

Before rendering or saving a report, make the source-status packet include `count`, `status`, `reason`, `retrieval_method`, `evidence_urls`, `runner_executed`, `terminal_success`, `evidence_retrieved`, and the applicable `usable_count`/body-evidence count, then run:

```bash
python3 scripts/validate_research_evidence.py \
  --input work/source-status.json \
  --require-core-4 \
  --out work/research-validation.json
```

The validator emits the immutable contract name `core4_strict_v1` and blockers in the fixed source order. If it fails, label the run `research_incomplete`, show the exact source/stage/reason blocker (`auth_required`, `blocked`, `no_results`, `not_configured`, `error`, `runner_not_executed`, `terminal_failure`, `no_valid_evidence`, or `invalid_provenance`), and do not write or describe a completed cross-platform brief. A partial report may be written only when explicitly requested and must use the partial-save path; it is never a successful research completion. A `planned` source is never evidence. If the task is running in a background/automation session and there is no actual research turn or tool output, apply the same rule: report `research_incomplete` instead of implying that research occurred.

## Input modes

### Topic or question only

When the user gives no URL, infer the entities, products, people, dates, handles, subreddits, repositories, and disputed terms in the question. Create the mandatory query families from the default research depth: original wording, Japanese, English, synonyms/related terms, exact names, official/primary source, news, implementation/tutorial, experience/review, criticism/limitations, and counterargument/alternative view. Route the plan to YouTube, X, Reddit, ordinary Web search and page reading, GitHub, Hacker News, and RSS by default; add configured optional sources such as TikTok, Instagram, Bluesky, LinkedIn, arXiv, Polymarket, Bilibili, Xiaohongshu, Facebook, V2EX, Xiaoyuzhou, or Xueqiu when they are relevant and available.

When YouTube is relevant, search for multiple candidate videos rather than selecting the first result. Prefer a diverse set: independent creators, official/primary channels, specialist explainers, recent updates, and credible counterpoints. Deduplicate near-identical reposts and cap the set using the selected automatic mode, source health, relevance, date, and diversity available in the active adapter.

### One or more URLs

Run `scripts/plan_research.py --mode auto` first. A single X post, X thread, Reddit post, Reddit comment permalink, subreddit URL, or a mixture of these and other URLs is a valid input. Classify each URL and expand it into related evidence:

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
- `source_selection` metadata for core sources, optional candidates, and bounded seed expansion;
- `source_balance` metadata, including the non-YouTube corroboration requirement for YouTube-focused Standard/Deep plans;
- `collection_limits` metadata with per-source target, minimum, and maximum counts;
- the automatically selected mode and the reason for selecting it;
- whether the user wants facts, opinions, reactions, implementation evidence, market sentiment, or first-hand experiences.

Use the deterministic planner:

```bash
python3 scripts/plan_research.py \
  --mode auto \
  --question "ユーザーの質問" \
  "https://example.com/seed" \
  --out work/research-plan.json
```

Read [references/source-routing.md](references/source-routing.md) and `scripts/source_contract.py` to adjust source selection, canonical identities, host aliases, and YouTube diversity for the topic. Do not silently omit a source because it is harder to access; mark its status and continue with the available sources.

### 2. Check source health and select adapters

Use the current installed contracts rather than inventing undocumented command syntax. These are internal acquisition routes for this Skill; the user should invoke this Skill once rather than manually combining separate tools:

| Layer | Preferred tool | Role |
| --- | --- | --- |
| Access and routing | Agent-Reach | YouTube subtitles/transcription, public GitHub, Web, and configured X/Reddit routes; run `agent-reach doctor` when available |
| Cross-source discovery and synthesis | last30days-skill | Recent discovery, engagement-aware ranking, cross-source clusters, and cited synthesis across its supported platforms |
| Reddit precision | PRAW | Repeatable read-only submissions/comments, scores, timestamps, subreddit filters, and exact API collection |
| YouTube fallback | `yt-dlp` plus bundled normalizer | Direct subtitle/caption retrieval first; Agent-Reach transcription only when explicitly selected or audio fallback is authorized |

Agent-Reach is an access layer, not proof that a source is complete. last30days-skill is a discovery/synthesis layer, not a substitute for opening primary URLs. PRAW is only for Reddit and never posts. Follow each installed upstream Skill's current `SKILL.md` and report unavailable routes.

For OpenCLI-backed read-only collection, pass `--window background --site-session persistent` by default. Persistent sessions intentionally keep and reuse the site's browser container, preventing each X/Reddit command from creating another visible `about:blank` Chrome window. Do not request ephemeral tab cleanup for this lane, and do not run parallel foreground OpenCLI sessions unless the user explicitly asks to watch the browser; X and Reddit remain separate authenticated site contexts internally.

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

The URL helper tries `yt-dlp` subtitles first, one requested language at a time, then English fallbacks (`en`, `en-US`, `en-GB`). A rate limit or missing track in one language must not prevent the next language attempt. `agent-reach transcribe` is an ASR/audio route and runs only when `--backend agent-reach` is explicitly selected or `--allow-audio` is supplied. Audio download plus `faster-whisper` requires the explicit `--allow-audio` decision. The helper applies one overall URL timeout, not a fresh full timeout for every backend/language attempt. Never silently download audio. Run the helper separately for each selected video and keep one manifest per video.

Do not reduce the YouTube result to a few transcript snippets. Build a per-video transcript index with `full`, `partial`, or `unavailable` status, transcript type/language, key timestamps, and the relative artifact path. Preserve the complete normalized transcript as a local artifact when available; summarize it in the chat instead of dumping the full text into the final response.

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

Use every query family in the plan, claim-specific and entity-specific, rather than one giant transcript query. Search the selected source set in parallel where the active tools allow it: YouTube, X, Reddit, Web, GitHub, Hacker News, and RSS. Add relevant optional sources from the plan. Do not skip a required query family in standard/deep mode merely because the first query returned results.

Use ordinary Web search for broad discovery, official documentation, news, blogs, Q&A, and primary pages. For GitHub, inspect Issues and Discussions rather than only the README. For Reddit, inspect comments and parent/reply context rather than only post titles. Use last30days-skill for recent cross-source discovery according to its current contract. Use Agent-Reach or the configured official/API adapter for retrieval. Use PRAW when Reddit comments, scores, timestamps, or subreddit filtering need precise repeatability. Open and preserve primary URLs for important claims; a search snippet alone is not equivalent to a source.

Keep first-hand experiences separate from official documentation, maintainer claims, and commentary. Record author, date, platform, direct URL, quoted passage, engagement context, and retrieval method without exposing credentials.

### 6. Normalize the evidence ledger

Convert adapter outputs to [references/evidence-schema.md](references/evidence-schema.md):

```bash
python3 scripts/normalize_evidence.py \
  --input work/raw-evidence.jsonl \
  --output work/evidence.jsonl \
  --topic "調査テーマ"
```

At minimum preserve `source`, `url`, `published_at`, `retrieved_at`, `author`, `title`, `text`, `quote`, `engagement`, `claim_ids`, `retrieval_method`, `source_role`, and `confidence`. Keep source status and error details in the ledger; do not turn an auth failure into `no_results`.

### 7. Write the final brief

Before the conclusion, create a source-status JSON packet and render it with:

```bash
python3 scripts/render_coverage.py \
  --input work/source-status.json \
  --out work/coverage.md
```

The packet must contain one record per planned source with `source`, `status`, `count`, `reason`, and preferably `retrieval_method` or `evidence_quality`. Use the exact statuses `complete`, `partial`, `auth_required`, `blocked`, `no_results`, `not_configured`, or `error`. Put the rendered coverage block at the very top of the final answer, before the conclusion. Never represent an unavailable source as zero results without its reason.

Use [references/report-template.md](references/report-template.md) and report:

1. the source coverage block and automatically selected mode;
2. direct answer and confidence;
3. what was searched: question, URLs, date window, languages, platforms, and number of usable YouTube videos;
4. claim-by-claim findings with timestamped video links where applicable;
5. agreement, disagreement, and source-dependency across the multiple videos and other platforms;
6. first-hand experiences, official/maintainer statements, and commentary as separate categories;
7. practical implications and remaining uncertainty;
8. direct source links with retrieval dates.

After writing the brief, save it to the stable user directory with:

```bash
python3 scripts/save_report.py \
  --input work/final-report.md \
  --coverage work/coverage.md \
  --artifacts-dir work/youtube \
  --validation work/research-validation.json \
  --topic "調査テーマ"
```

`save_report.py` refuses to save a completed report unless the validation JSON is valid. Use `--allow-partial` only when the report is explicitly labeled `research_incomplete` or `partial` and includes the exact source blocker.

The default directory is `~/Documents/Codex/Universal Research/reports/`. Create one package directory per run containing `report.md` and, when `work/youtube` exists, `artifacts/youtube/`. Copy only transcript/metadata artifacts; never copy cookies, tokens, raw auth files, or unrelated evidence. Preserve the per-video transcript status and relative artifact path in the YouTube index. Respect `UNIVERSAL_RESEARCH_REPORT_DIR` or `--report-dir` when the user has configured another local directory. Report the absolute saved report and package paths in the final answer.

Say `not corroborated in the searched window` when a claim lacks independent support. Say `the selected sources agree` rather than presenting repeated or copied content as universal truth.

## Failure handling

- If subtitles are absent for one video, continue with the other selected videos and offer explicit opt-in ASR for that video.
- If a source is not configured, blocked, login-required, rate-limited, or schema-drifted, preserve that status and continue with the other sources.
- If YouTube returns too few distinct videos, report the actual count and do not imply full multi-video coverage.
- If only one video is usable, explicitly downgrade confidence and identify the missing diversity.
- If a URL is inaccessible, use its host/path/title tokens for discovery but label the seed as inaccessible.
- If a claim depends on an exact quote, retain the timestamp and link to the original video or post.
- If the user asks for more depth, expand the date window, query variants, and source count before writing a stronger conclusion.
- If source collection succeeds but coverage rendering or report saving fails, report the research result as complete/partial separately from the local-save error and include the exact restart command.

## References

- Read [references/source-routing.md](references/source-routing.md) for topic/URL routing, platform expansion, and multi-video selection.
- Read [references/upstream-mapping.md](references/upstream-mapping.md) when choosing Agent-Reach, last30days-skill, and PRAW.
- Read [references/evidence-schema.md](references/evidence-schema.md) before writing or validating source records.
- Read [references/report-template.md](references/report-template.md) when producing a user-facing brief.
- Use `scripts/render_coverage.py` for the mandatory source-status header and `scripts/save_report.py` for the stable local report path.
- Use the upstream projects' current documentation: [Agent-Reach](https://github.com/Panniantong/Agent-Reach), [last30days-skill](https://github.com/mvanhorn/last30days-skill), and [PRAW](https://github.com/praw-dev/praw).
