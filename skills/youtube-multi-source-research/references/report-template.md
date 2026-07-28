# Report template

Use this outline for the final Japanese research brief. Keep the first screen useful: do not make the reader search through a long comparison table to find the recommendation.

```markdown
# 調査レポート：<テーマ>

## 調査状況（自動選択モード: standard）

| 媒体 | 状態 | 取得件数 | 取得方法・根拠 | 未取得理由 |
| --- | --- | ---: | --- | --- |
| YouTube | `complete` | 8 | yt-dlp / 字幕 | — |

## 先に結論

### あなた向けの判断

- 第一候補：<用途に対する候補>
- 使い分け：<2〜4行>
- 今回の結論の確度：高 / 中 / 低

### 1分で分かる要点

- <要点1>
- <要点2>
- <要点3>

## 比較サマリー

Keep cells short. Put long evidence in the detail sections below.

| 候補 | 向いている用途 | 推奨度 | 主な根拠 | 注意点 |
| --- | --- | --- | --- | --- |
| <tool> | <use case> | A/B/C | <official / experience / test> | <main risk> |

## YouTube字幕・台本素材

List every selected video, not only the videos used in the conclusion. Preserve the full normalized transcript under `artifacts/youtube/<video-id>/` when available; do not paste every transcript into the chat response.

| # | 動画 | チャンネル | 字幕状態 | 種類・言語 | 重要タイムスタンプ | 保存先 |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | <title/link> | <channel> | `full` / `partial` / `unavailable` | manual / generated / asr, ja/en | 00:00:00, ... | `artifacts/youtube/<id>/` |

For material claims, include the timestamp and distinguish official demo, tutorial, independent test, commentary, and repost. Do not count copied videos as independent evidence.

## 媒体別の生の声と一次情報

### 公式・一次情報

Summarize specifications, prices, limits, release notes, and official claims separately.

### X

Separate direct observations, self-reports, promotional posts, and claims that lack reproduction details.

### Reddit

Include post/comment context, parent/reply context, and whether the report is a first-hand experience or hearsay.

### GitHub・通常Web

Separate README/maintainer claims, Issues/Discussions, documentation, independent tests, and news/blog commentary.

## 台本に使える論点

1. <hook or factual angle>
2. <comparison or conflict>
3. <real user problem>
4. <counterargument and nuance>

Mark a claim as `未検証` or `検索期間内で裏付けなし` when the source set does not independently support it.

## 詳細な主張比較

| Claim | 出典・タイムスタンプ | 根拠の種類 | 反証・反対意見 | 判定 |
| --- | --- | --- | --- | --- |
| claim-001 | <URL + timestamp> | 公式 / 体験 / テスト | <counter-evidence> | verified / mixed / uncorroborated |

## 取得範囲と限界

List complete, partial, auth-required, blocked, no-results, and not-configured sources. Do not write only `0`; include the source status and reason. State when X/Reddit evidence came from a downstream researcher report rather than a directly reproduced raw capture.

## 主要ソース

Use direct original URLs and retrieval dates. Keep source method visible where it changes confidence.
```
