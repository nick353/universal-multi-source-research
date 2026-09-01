# Universal Multi-Source Research

OpenCLI-backed collection reuses persistent background site sessions so research does not open a new visible Chrome window for every source command.

Standard/deep runs have a live retrieval gate: X and Reddit are checked through a bounded OpenCLI read-only search, their source-native URLs are preserved, and a validator rejects a completed claim when required sources are only planned, configured, or mentioned without evidence.

Codex Skill for researching a topic, question, one or more URLs, or an existing transcript across every relevant configured platform. It includes ordinary Web search and page reading, automatically includes multiple YouTube videos when YouTube is relevant, then compares claims with X, Reddit, GitHub, Hacker News, RSS, and configured optional sources. X post/thread URLs and Reddit post/comment/subreddit URLs are supported seeds.

The package slug is `youtube-multi-source-research` for compatibility. The display name is **Universal Multi-Source Research**.

このSkillが調査の入口・媒体選択・主張比較・レポート作成を担当します。利用者がSkill名を書かずに「リサーチして」「調査して」「調べて」と依頼した場合も、このSkillを自動選択します。媒体取得のための内部ランタイムを利用しますが、利用者は個別の媒体ごとに別のSkillを組み合わせて呼び出す必要はありません。バンドルされたスクリプトは、調査計画、台本正規化、台本分割、共通証拠JSONL、英語のランタイム診断を安定して処理します。

通常の公開・読み取り専用リサーチは、媒体ごとの承認確認なしで自動開始します。ログイン、非公開・有料データ、投稿・送信・購入・権限変更・破壊操作は別の承認またはユーザー操作が必要です。

インストール後、初回だけ英語の診断アダプターを実行してください。YouTube、通常Web、RSS、公開GitHubは環境によってすぐ使えます。XとRedditはログイン状態や読み取り設定が必要な場合があります。Cookie・APIキー・トークンはチャットへ貼らず、利用者のローカル環境だけで設定してください。システムの設定・ログイン・成功/失敗通知は英語で表示し、研究レポート本文は日本語を標準にします。

The skill automatically selects quick, standard, or deep research from the request. It targets 3–5, 5–10, or 8–12 YouTube videos respectively, while keeping platform selection automatic. Standard/deep research includes ordinary Web search, official/news/blog/Q&A/primary sources, GitHub Issues/Discussions, Reddit comments, and Japanese/English/synonym/experience/criticism/counterargument query families.

Standard/deep plans include the optional candidate identities TikTok, Instagram, Bluesky, LinkedIn, arXiv, Polymarket, Bilibili, Xiaohongshu, Facebook, V2EX, Xiaoyuzhou, and Xueqiu without requiring the user to say “all platforms”.

They also include source-specific `collection_limits` for target, minimum, and maximum counts so X and other non-YouTube sources are not left to an unspecified result volume.

The final answer starts with a source coverage table containing status, item counts, and reasons for unavailable sources, followed by a short recommendation, compact comparison, and script-ready YouTube/transcript index. Completed reports and available transcript artifacts are saved by default to `~/Documents/Codex/Universal Research/reports/`.

Read `SKILL.md` for the workflow, `references/source-routing.md` for platform and multi-video policy, and `references/evidence-schema.md` before writing evidence records.
