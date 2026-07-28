import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class SkillScriptsTest(unittest.TestCase):
    def test_vtt_normalization_and_chunking(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "source.vtt"
            source.write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello <b>world</b>\n\n00:00:04.000 --> 00:00:06.000\nSecond line\n",
                encoding="utf-8",
            )
            transcript_dir = work / "transcript"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "extract_transcript.py"), "--input", str(source), "--out", str(transcript_dir)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            transcript = json.loads((transcript_dir / "transcript.json").read_text(encoding="utf-8"))
            self.assertEqual(len(transcript), 2)
            self.assertEqual(transcript[0]["text"], "Hello world")
            chunks = work / "chunks.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "chunk_transcript.py"), str(transcript_dir / "transcript.json"), "--out", str(chunks), "--max-chars", "100"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(json.loads(chunks.read_text(encoding="utf-8"))), 1)

    def test_evidence_normalization(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "raw.json"
            source.write_text(
                json.dumps([
                    {"platform": "reddit", "url": "https://www.reddit.com/r/test/x", "body": "A real experience", "upvotes": 12, "claim_id": "claim-001", "retrieval_method": "praw"}
                ]),
                encoding="utf-8",
            )
            output = work / "evidence.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "normalize_evidence.py"), "--input", str(source), "--output", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertEqual(record["source"], "reddit")
            self.assertEqual(record["engagement"]["score"], 12)
            self.assertEqual(record["claim_ids"], ["claim-001"])
            self.assertEqual(record["confidence"], "high")

    def test_research_plan_expands_a_youtube_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plan.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plan_research.py"),
                    "https://www.youtube.com/watch?v=abc123",
                    "--question",
                    "Geminiの最新機能を調査",
                    "--out",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(plan["seeds"][0]["type"], "youtube")
            sources = {record["source"] for record in plan["sources"]}
            self.assertTrue({"youtube", "x", "reddit", "web", "github"}.issubset(sources))
            self.assertEqual(plan["youtube_policy"]["minimum_distinct_count"], 5)
            self.assertEqual(plan["mode"], "deep")
            self.assertEqual(plan["youtube_policy"]["target_count"], 8)
            self.assertTrue(plan["web_policy"]["ordinary_search_required"])
            self.assertTrue(plan["community_policy"]["reddit_comments_required"])
            self.assertTrue(plan["community_policy"]["github_issues_required"])
            families = {family["id"] for family in plan["query_families"]}
            self.assertTrue({"japanese", "english", "synonyms", "counterargument"}.issubset(families))
            self.assertTrue(any("counterargument" in query for query in plan["queries"]))

    def test_broad_question_adds_configured_optional_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plan.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plan_research.py"),
                    "--question",
                    "全プラットフォームで調査",
                    "--out",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            sources = {record["source"] for record in plan["sources"]}
            self.assertTrue({"tiktok", "bluesky", "arxiv", "bilibili"}.issubset(sources))

    def test_x_and_reddit_urls_are_valid_cross_platform_seeds(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plan.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plan_research.py"),
                    "https://x.com/example/status/123",
                    "https://www.reddit.com/r/example/comments/abc123/example/",
                    "--question",
                    "この投稿内容を検証",
                    "--out",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([seed["type"] for seed in plan["seeds"]], ["x", "reddit"])
            sources = {record["source"] for record in plan["sources"]}
            self.assertTrue({"youtube", "x", "reddit", "web", "github"}.issubset(sources))
            web_record = next(record for record in plan["sources"] if record["source"] == "web")
            self.assertIn("ordinary web search", web_record["retrieval_role"])
            reddit_record = next(record for record in plan["sources"] if record["source"] == "reddit")
            github_record = next(record for record in plan["sources"] if record["source"] == "github")
            self.assertIn("comments", reddit_record["collection_targets"])
            self.assertIn("Issues", github_record["collection_targets"])
            self.assertIn("Discussions", github_record["collection_targets"])

    def test_user_setup_guidance_is_present(self):
        plugin_readme = ROOT.parents[1] / "README.md"
        text = plugin_readme.read_text(encoding="utf-8")
        self.assertIn("インストール後に必要な初回設定", text)
        self.assertIn("agent-reach doctor", text)
        self.assertIn("XやReddit", text)
        self.assertIn("Cookie、APIキー、トークンはチャットに貼らない", text)

    def test_auto_mode_selects_quick_standard_and_deep(self):
        cases = [
            ("これは何ですか？要点だけ教えて", "quick", 3),
            ("Geminiの使い方を調査して", "standard", 5),
            ("最新のAI動画生成ツールをYouTube、X、Redditで比較して台本用に調査", "deep", 8),
        ]
        for question, expected_mode, expected_target in cases:
            with self.subTest(question=question):
                with tempfile.TemporaryDirectory() as temp:
                    output = Path(temp) / "plan.json"
                    result = subprocess.run(
                        [sys.executable, str(SCRIPTS / "plan_research.py"), "--question", question, "--out", str(output)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    plan = json.loads(output.read_text(encoding="utf-8"))
                    self.assertEqual(plan["mode"], expected_mode)
                    self.assertTrue(plan["mode_selection"]["automatic"])
                    self.assertEqual(plan["youtube_policy"]["target_count"], expected_target)
                    if expected_mode == "quick":
                        self.assertEqual(len(plan["query_families"]), 5)
                    else:
                        self.assertEqual(len(plan["query_families"]), 12)

    def test_coverage_render_and_stable_report_save(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            status = work / "source-status.json"
            status.write_text(
                json.dumps(
                    {
                        "mode": "standard",
                        "sources": [
                            {"source": "youtube", "status": "complete", "count": 8, "reason": ""},
                            {"source": "x", "status": "auth_required", "count": 0, "reason": "Cookie設定が必要"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            coverage = work / "coverage.md"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "render_coverage.py"), "--input", str(status), "--out", str(coverage)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            coverage_text = coverage.read_text(encoding="utf-8")
            self.assertTrue(coverage_text.startswith("## 調査状況（自動選択モード: standard）"))
            self.assertIn("| X | `auth_required` | 0 | Cookie設定が必要 |", coverage_text)

            report = work / "final-report.md"
            report.write_text("## Conclusion\nテスト結果\n", encoding="utf-8")
            report_dir = work / "reports"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "save_report.py"),
                    "--input",
                    str(report),
                    "--coverage",
                    str(coverage),
                    "--topic",
                    "AI動画調査",
                    "--report-dir",
                    str(report_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(result.stdout)["path"]
            saved_path = Path(saved)
            self.assertEqual(saved_path.parent, report_dir.resolve())
            self.assertTrue(saved_path.exists())
            self.assertTrue(saved_path.read_text(encoding="utf-8").startswith("## 調査状況"))


if __name__ == "__main__":
    unittest.main()
