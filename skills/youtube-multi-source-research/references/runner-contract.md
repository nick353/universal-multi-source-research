# Common runner contract

This document defines the adapter-neutral contract implemented by
`scripts/research_runner.py`. The runner owns one research ledger, its mode and
query-family receipts, the fixed core-source order, and the final fail-closed
validation. Source adapters own provider-specific retrieval and return terminal
status packets to the runner.

The contract version is `universal_research_run.v1`. The ordinary completion
contract is `core4_strict_v1` for the following required sources, in this exact
order:

```text
youtube -> x -> reddit -> web
```

`web` means ordinary Web search plus opened page evidence. A URL candidate,
search snippet, page that only mentions another platform, or an adapter's
health result is not Web evidence. Standard and Deep plans may contain optional
sources after the core four; optional sources never replace a core source.

## Lifecycle

```text
start
  -> record youtube (terminal packet)
  -> record x       (terminal packet)
  -> record reddit  (terminal packet)
  -> record web     (terminal packet)
  -> finalize       (mode + query + evidence gate)
```

### 1. `start`

Start one run before any source adapter is called:

```bash
python3 scripts/research_runner.py start \
  --mode auto --question "<topic>" --work-dir work
```

`start` calls the deterministic planner and creates one shared `run_id` in:

- `research-plan.json` — selected mode, query families, sources, and limits;
- `source-status.json` — the mutable source ledger, initially `planned`;
- `research-run.json` — run metadata and output paths.

The selected mode is always `quick`, `standard`, or `deep`; `auto` is only the
start-time selection input. The plan and status copy the selected mode,
`required_sources`, `source_order`, and completion contract. Until a valid
finalization, the run status is `research_incomplete`. A work directory that
already contains run files is rejected unless replacement is explicitly
requested with `--force`.

### 2. `record`

Record only after the source adapter has finished with a terminal result:

```bash
python3 scripts/research_runner.py record \
  --work-dir work --source youtube --packet work/youtube-status.json \
  --query-family exact --query-family japanese
```

For core sources, `record` enforces the next planned source in the fixed order:
YouTube, then X, then Reddit, then ordinary Web. A packet for a core source
cannot skip ahead. An optional planned source may be recorded as well, but it
does not advance or replace the core sequence.

The packet may be one source object or an object with a `sources` array. When
the array form is used, it must contain exactly one record for the `--source`
value. If a packet supplies `run_id`, it must equal the run's `run_id`.
Protected run metadata cannot be supplied by an adapter packet:
`contract_version`, `run_id`, `research_mode`, `mode`, `mode_selection`,
`required_sources`, `source_order`, and `completion_contract`.

`record` accepts only these terminal statuses:

```text
complete | partial | auth_required | blocked | no_results | not_configured | error
```

`planned` is a ledger state, not a terminal adapter result, and is rejected by
`record`. Recording a terminal result does not make the overall research run
complete; only `finalize` can make that decision.

### 3. `finalize`

Finalize only after all available core adapters have returned terminal packets:

```bash
python3 scripts/research_runner.py finalize --work-dir work
```

`finalize` validates the exact plan and status together. It requires the four
core sources to be complete, actually executed, terminal-successful, backed by
source-native evidence, and above the selected mode's evidence floors. It also
requires every query family marked required by the selected plan to have an
execution receipt. It writes `research-validation.json` and `coverage.md` even
when validation fails, so the exact incomplete source and blocker remain
visible.

On success, `source-status.json` and `research-run.json` receive status
`complete`, and the command exits zero. On failure, the run remains
`research_incomplete` and the command exits non-zero. Finalization sets a
completion timestamp even for an invalid result; do not try to mutate that run
afterward. Preserve the evidence and start a new run when a new ledger is
needed.

## Terminal source packet

A packet intended to satisfy the core completion gate has this shape. A flat
source object and a one-record `sources` wrapper are both accepted. The example
uses the wrapper form so the optional packet-level `run_id` is kept separate
from the source record.

```json
{
  "run_id": "research-...",
  "sources": [{
    "source": "youtube",
    "status": "complete",
    "count": 8,
    "usable_count": 5,
    "evidence_urls": ["https://www.youtube.com/watch?v=..."],
    "reason": "transcripts and metadata retrieved",
    "retrieval_method": "yt-dlp subtitles",
    "runner_executed": true,
    "terminal_success": true,
    "evidence_retrieved": true,
    "query_families_executed": ["exact", "japanese"]
  }]
}
```

The fields have these meanings:

| Field | Contract |
| --- | --- |
| `source` | One planned source ID. It must agree with `--source`; the runner never accepts a packet for a different source. |
| `status` | One of the terminal statuses above. `complete` claims usable retrieval; the final validator still checks the supporting fields. |
| `count` | Non-negative integer count of candidates/items. A complete source must have a positive count and URL evidence. |
| `evidence_urls` | An array of valid HTTP(S) evidence URLs. YouTube, X, and Reddit need at least one URL on their own platform; Web needs opened page URLs. |
| `reason` | Short, source-specific explanation of success, shortfall, authentication, blocking, no results, or error. Preserve the exact reason for unavailable coverage. |
| `retrieval_method` | Non-empty provenance string naming how the adapter obtained the result. |
| `runner_executed` | `true` only when the dedicated source runner actually ran. A plan entry or health check is not execution proof. |
| `terminal_success` | `true` only when the adapter reached successful terminal retrieval. An adapter can return a terminal failure status without terminal success. |
| `evidence_retrieved` | `true` only when evidence was actually obtained, not merely planned or discovered as a candidate. |
| `usable_count` | Required for YouTube. It is the explicit count of videos with usable transcript or verified metadata evidence; candidate `count` alone never satisfies YouTube. |
| `body_evidence_count` or `content_records` | Required for X, Reddit, and Web when claiming core completion. It must be positive and represent post/comment body or opened-page content, not URLs alone. |
| `query_families_executed` | Optional at packet level, but any supplied IDs are merged into the run ledger and must exist in the selected plan. The CLI `--query-family` may supply the same receipt. |
| `run_id` | Optional at the packet wrapper level, but if present it must exactly match the run. Keep it out of the inner source record because run metadata is protected. |

For a non-success terminal result, keep the packet honest: use zero/empty
evidence counts as appropriate, set `terminal_success` and
`evidence_retrieved` to `false` when no successful evidence exists, and explain
the boundary in `reason`. The runner records the result for diagnosis; it does
not convert it to a successful source.

## Fixed source and evidence rules

The core source IDs are immutable for an ordinary run:

```json
["youtube", "x", "reddit", "web"]
```

Every core record must prove all of the following before `finalize` can pass:

- `status` is `complete`;
- `runner_executed`, `terminal_success`, and `evidence_retrieved` are `true`;
- `count` is positive;
- `evidence_urls` contains valid HTTP(S) URLs, including a source-native URL
  for YouTube, X, or Reddit;
- `retrieval_method` is non-empty;
- YouTube has a positive explicit `usable_count`;
- X, Reddit, and Web have a positive `body_evidence_count` or
  `content_records`.

The runner does not infer body evidence from URL count, candidate count, or
search snippets. It does not infer YouTube usability from the number of video
URLs. Copied or reposted material is not independent corroboration merely
because it has a different URL.

## Quick, Standard, and Deep validation

The planner stores target, minimum, and maximum counts. `finalize` enforces the
minimum evidence floors below; targets and maximums remain collection guidance
for the adapter.

| Mode | YouTube items | X primary posts | Reddit submissions | Web opened pages |
| --- | --- | --- | --- | --- |
| Quick | target 3, min 2, max 5 | target 2, min 2, max 5 | target 2, min 2, max 5 | target 3, min 1, max 6 |
| Standard | target 5, min 3, max 10 | target 10, min 5, max 20 | target 5, min 3, max 10 | target 12, min 8, max 15 |
| Deep | target 8, min 5, max 12 | target 20, min 10, max 40 | target 10, min 5, max 20 | target 20, min 12, max 25 |

For mode validation, the plan and status must share the same `run_id`, selected
mode, and fixed required-source declaration. The status `research_mode` must
match the plan; if status `mode` is present, it must match as well. A shortfall
is a mode blocker, not permission to silently downgrade the mode or report a
smaller collection as complete.

Required query families are mode-specific:

- **Quick:** `exact`, `japanese`, `official`, `experience`, `criticism`,
  `reddit_comments`.
- **Standard:** `exact`, `japanese`, `english`, `synonyms`, `official`, `news`,
  `implementation`, `experience`, `criticism`, `counterargument`,
  `reddit_comments`, `github_discussions`.
- **Deep:** the same twelve families as Standard.

The runner accumulates distinct family IDs from terminal packets and repeated
`--query-family` flags. An unknown ID fails immediately with a plan-mismatch
error. `finalize` fails with `query_family_not_executed` until every required
family is present. A family receipt proves that the family was recorded; it does
not by itself prove that a provider returned evidence.

## Authentication, rate limits, and other boundaries

The common runner is read-only and credential-free. It does not log in, create
credentials, read private or paid data, post, send, purchase, change
permissions, or perform destructive actions. Do not put cookies, API keys,
OAuth tokens, passwords, or other secrets in packets or reports.

Use the exact status that describes the adapter boundary:

| Status | Use when | Do not do |
| --- | --- | --- |
| `auth_required` | Login, an API credential, or another user-controlled authentication step is required. | Do not paste credentials into chat or pretend the source has no results. |
| `blocked` | Rate limit, CAPTCHA, HTTP 403, robots restriction, platform restriction, or equivalent provider refusal prevents retrieval. | Do not relabel it `no_results` or silently claim a fallback source fulfilled it. |
| `no_results` | The adapter successfully queried the source and found no usable result. | Do not use it for a skipped, unauthenticated, or rate-limited adapter. |
| `not_configured` | The adapter is absent, disabled, or not enabled in the environment. | Do not treat plan presence or an installation name as retrieval. |
| `partial` | The adapter finished but only some requested evidence or fields were available. | Do not promote it to complete at finalization. |
| `error` | An unexpected adapter or parsing failure occurred. | Preserve the diagnostic reason and do not conceal it as no results. |

The runner may record these terminal outcomes so coverage is explicit, but a
required core source with any of them fails the strict completion gate. Continue
with other in-scope read-only sources when appropriate and report the exact
source/status/reason; never replay an unknown external effect merely to obtain a
better packet.

## Adapter packets are not magic provider access

A packet is a bounded adapter result, not a capability token. Supplying JSON
with a provider name, URL, `configured: true`, or `status: complete` does not
log in, bypass a rate limit, fetch a page, or create source-native evidence.
The runner does not call Agent-Reach, yt-dlp, OpenCLI, PRAW, Web search, or any
other provider route on an adapter's behalf. It records what the adapter says
and then validates the independently meaningful execution and evidence fields.

Therefore:

1. Run the actual source adapter before `record`.
2. Preserve source-native URLs and body/transcript evidence counts.
3. Record authentication, blocking, configuration, and no-result boundaries
   truthfully.
4. Treat `finalize` as the only completion decision; a plan, accepted packet,
   health check, or queued adapter call is not completion proof.
