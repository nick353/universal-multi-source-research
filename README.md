# Universal Multi-Source Research Codex Plugin

Codex App plugin for a read-only, topic-first research workflow. The package slug remains `youtube-multi-source-research` so existing installs and prompts continue to work; the display name is **Universal Multi-Source Research**.

```text
topic / question / one or more URLs / transcript
  -> automatic source routing
  -> multiple YouTube videos when relevant
  -> X / Reddit / Web / GitHub / Hacker News / RSS and configured optional sources
  -> claim comparison, first-hand voices, and cited research brief
```

このプラグインが主役となって、調査テーマ・質問・URLから取得先を自動選択し、複数媒体の情報をまとめます。媒体接続のための取得ランタイムは内部で利用しますが、利用者は個別の媒体ごとに別のSkillを呼び出す必要はありません。システムの診断・設定・ログイン・成功/失敗通知は英語で表示し、調査レポート本文は日本語を標準にします。

## 4媒体の完了保証

通常の非限定リサーチでは、YouTube・X・Reddit・通常Webを必須媒体として扱います。検索計画や検索スニペットだけでは完了にならず、各媒体の専用runner実行、terminal成功、本文付きの媒体固有URL、取得方法を最終ゲートで検証します。YouTubeは個別字幕または検証済みメタデータ、Webは開いたページ本文、X/Redditは投稿・コメント本文が必要です。

1媒体でも未設定、ログイン要求、ブロック、タイムアウト、本文なしになった場合は `research_incomplete` として報告し、Webだけで代替した完了レポートは保存しません。最終検証契約は `core4_strict_v1` です。明示的に媒体を限定した依頼は、その指定された範囲で実行します。

## What it does

You can say “このテーマを調査して” without naming a Skill or listing platforms. The Skill plans YouTube, X, Reddit, ordinary Web search and page reading, GitHub, Hacker News, and RSS, then adds relevant configured sources. Ordinary Web search includes official sites, documentation, news, blogs, Q&A, and primary sources. A URL can be a YouTube, X, Reddit, GitHub, article, PDF, channel, playlist, or a mixture of URLs.

The `$youtube-multi-source-research` form remains available as an explicit override, but it is not required. An explicit request such as “Webだけ” or “このYouTube動画1本だけ” still narrows the scope.

An X post/thread URL or Reddit post/comment/subreddit URL is a valid seed. The Skill reads the seed and expands to linked sources, related YouTube videos, other community discussions, ordinary Web results, and GitHub evidence when relevant.

YouTube is treated as a source family, not one citation. For relevant topics, the default target is 5–10 diverse videos, with a minimum quality target of three distinct videos when coverage exists. It compares channels, dates, transcripts, claims, primary-source citations, repeated content, and counterpoints. If fewer videos or transcripts are available, the final report says so and lowers confidence.

調査の深さはユーザーに選ばせず、依頼内容から自動判定します。短い事実確認は簡易調査、通常のテーマやURLは標準調査、比較・最新情報・評判・実体験・台本作成・複数URLなどは深掘り調査になります。媒体の選択もテーマとURLから自動で行います。

The default depth also requires ordinary Web search, official/news/blog/Q&A/primary pages, GitHub Issues and Discussions, Reddit comments and reply context, plus Japanese, English, synonym, experience, criticism, and counterargument query families. These are part of the standard plan, not optional add-ons.

Every final answer starts with a source coverage table showing each platform's status, item count, and any setup/block reason. The first screen then gives a short recommendation, a compact comparison, and script-ready YouTube points. Completed reports and available transcript artifacts are saved by default to `~/Documents/Codex/Universal Research/reports/`.

## Use in Codex App

```text
Use $youtube-multi-source-research to research this topic across every relevant configured platform:
「ここにテーマ、質問、または比較したい論点」
```

With one or more URLs:

```text
Use $youtube-multi-source-research to investigate these URLs and expand the research across all relevant platforms:
https://www.youtube.com/watch?v=VIDEO_ID
https://github.com/OWNER/REPO
```

For a single-video-only task, explicitly say “このYouTube動画1本だけを調査”. Otherwise a supplied YouTube URL is expanded into related videos and cross-platform corroboration.

## インストール後に必要な初回設定

このプラグインをインストールしただけで、調査の指示・計画・Web/YouTube/GitHub/RSSの基本取得は始められます。ただし、XやRedditのログインが必要な情報は、利用者自身の環境で一度だけ接続設定が必要です。

最初の実行時に、次の確認をしてください。

```bash
python3 skills/youtube-multi-source-research/scripts/agent_reach_status.py --json
```

表示された媒体の状態に従って設定します。

- YouTube、通常Web、RSS、公開GitHub：環境によっては追加設定なしで利用可能
- X：ブラウザから取得したCookieを、ローカル端末で明示的に設定
- Reddit：ログイン済みのブラウザ接続、または読み取り専用APIを設定
- 未設定・ログイン要求・ブロック中の媒体：調査結果で状態を明示し、検索できたことにはしない

Cookie、APIキー、トークンはチャットに貼らないでください。必要な設定は利用者のローカル環境で行います。設定後は新しいCodexタスクを開き、次のように実行できます。

```text
Universal Multi-Source Researchで、このテーマを全媒体調査して。
```

モードを指定する必要はありません。必要ならURLや「台本用」「直近30日」など目的だけを追加してください。

設定が不足している場合、このSkillは「インストール済みだが、追加設定が必要な媒体」を利用者へ案内します。

## Install after publishing

For Codex or another Agent Skills host:

```bash
npx skills add <owner>/youtube-multi-source-research -g -a codex
```

この公開リポジトリから直接インストールする場合：

```bash
npx skills add nick353/universal-multi-source-research -g -a codex
```

取得ランタイムの追加設定が必要な場合は、インストール時に表示される案内に従ってください。APIキーやCookieをこのリポジトリへ保存しないでください。

## Local smoke test

```bash
python3 -m unittest discover -s skills/youtube-multi-source-research/tests -v
python3 skills/youtube-multi-source-research/scripts/plan_research.py \
  --question "テーマを全媒体で調査" \
  "https://www.youtube.com/watch?v=VIDEO_ID" \
  --out work/research-plan.json
```

Normalize a local transcript:

```bash
python3 skills/youtube-multi-source-research/scripts/extract_transcript.py \
  --input ./example.vtt \
  --out ./work/transcript
python3 skills/youtube-multi-source-research/scripts/chunk_transcript.py \
  ./work/transcript/transcript.json \
  --out ./work/transcript/chunks.json
```

## Safety and source integrity

- Read-only by default; no posting or account actions are implemented.
- Cookies, tokens, and API keys are not written to evidence or reports.
- Every evidence record retains retrieval method, timestamp, URL, and status.
- A failed or unauthenticated source is reported as partial coverage, not as no evidence.
- Reposts and copied claims are not independent corroboration.
- Engagement numbers help rank attention but do not prove a claim.

## Project status

This repository is an integration Skill, not a replacement for any upstream platform adapter. Platform APIs, login requirements, and upstream CLI behavior can change. Follow each upstream project's current README and terms before enabling an authenticated source.
