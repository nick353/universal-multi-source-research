# Universal Multi-Source Research

Codex Skill for researching a topic, question, one or more URLs, or an existing transcript across every relevant configured platform. It includes ordinary Web search and page reading, automatically includes multiple YouTube videos when YouTube is relevant, then compares claims with X, Reddit, GitHub, Hacker News, RSS, and configured optional sources. X post/thread URLs and Reddit post/comment/subreddit URLs are supported seeds.

The package slug is `youtube-multi-source-research` for compatibility. The display name is **Universal Multi-Source Research**.

このSkillが調査の入口・媒体選択・主張比較・レポート作成を担当します。媒体取得のための内部ランタイムを利用しますが、利用者は個別の媒体ごとに別のSkillを組み合わせて呼び出す必要はありません。バンドルされたスクリプトは、調査計画、台本正規化、台本分割、共通証拠JSONLを安定して処理します。

インストール後、初回だけ`agent-reach doctor`を実行してください。YouTube、通常Web、RSS、公開GitHubは環境によってすぐ使えます。XとRedditはログイン状態や読み取り設定が必要な場合があります。Cookie・APIキー・トークンはチャットへ貼らず、利用者のローカル環境だけで設定してください。

The standard plan targets 5–10 YouTube videos, ordinary Web search, official/news/blog/Q&A/primary sources, GitHub Issues/Discussions, Reddit comments, and Japanese/English/synonym/experience/criticism/counterargument query families.

Read `SKILL.md` for the workflow, `references/source-routing.md` for platform and multi-video policy, and `references/evidence-schema.md` before writing evidence records.
