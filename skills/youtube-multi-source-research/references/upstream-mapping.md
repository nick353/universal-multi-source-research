# Upstream mapping

This skill is a universal topic/URL research integration layer. It does not copy code from the upstream projects. It uses their current contracts as separate access, discovery, and source-specific layers, while the local Skill owns source routing, multi-YouTube comparison, evidence normalization, and report structure.

## Agent-Reach

Repository: <https://github.com/Panniantong/Agent-Reach>

Use it as the access and routing layer. Its current README describes YouTube subtitle extraction and search, public GitHub access, Web reading, an `agent-reach doctor` health check, and configurable X/Reddit routes. Its release history also documents `agent-reach transcribe <link or file>` as an audio/video transcription fallback.

Important boundary: Agent-Reach routes to upstream CLIs and browser/API backends. It does not itself establish that a source returned complete evidence, and its authenticated X/Reddit paths can be affected by cookies, login state, platform changes, or account restrictions.

## last30days-skill

Repository: <https://github.com/mvanhorn/last30days-skill>

Use it as the discovery, ranking, cross-source clustering, and synthesis layer. Its current skill specification covers recent research across Reddit, X, YouTube, TikTok, Hacker News, Polymarket, GitHub, and the Web, with engagement-aware results and source health reporting.

Important boundary: it is topic-first research, not a guaranteed arbitrary-YouTube-URL-to-verbatim-transcript service. Feed it claim-specific queries and keep its source status separate from the final evidence ledger.

## PRAW

Repository: <https://github.com/praw-dev/praw>

Use it as the Reddit-specific collection adapter when exact submissions, comments, scores, timestamps, subreddit filters, or repeatable Python access are needed. PRAW follows Reddit's API model and supports read-only public analysis with an OAuth application and descriptive User-Agent.

Important boundary: PRAW does not search X, YouTube, GitHub, or the Web, and it does not write the final report. This skill never calls PRAW posting or reply methods.

## Selection rule

| Need | Select |
| --- | --- |
| Start from a YouTube URL | Agent-Reach, with bundled transcript normalizer |
| Search recent community reactions across several platforms | last30days-skill |
| Capture Reddit comments and scores precisely | PRAW |
| Lowest-complexity initial setup | Agent-Reach + last30days-skill |
| Most repeatable Reddit-only dataset | PRAW |

## Upstream links

- [Agent-Reach README](https://github.com/Panniantong/Agent-Reach#readme)
- [Agent-Reach releases](https://github.com/Panniantong/Agent-Reach/releases)
- [last30days README](https://github.com/mvanhorn/last30days-skill#readme)
- [last30days current skill specification](https://github.com/mvanhorn/last30days-skill/blob/main/skills/last30days/SKILL.md)
- [PRAW README](https://github.com/praw-dev/praw#readme)
- [PRAW documentation](https://praw.readthedocs.io/en/stable/)
- [Reddit Data API policy](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
