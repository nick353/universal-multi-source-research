import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class SkillScriptsTest(unittest.TestCase):
    def run_plan(self, *arguments: str) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "plan.json"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "plan_research.py"), *arguments, "--out", str(output)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(output.read_text(encoding="utf-8"))

    def core4_packet(self, missing: str | None = None) -> dict:
        records = [
            {
                "source": "youtube",
                "status": "complete",
                "count": 3,
                "usable_count": 2,
                "evidence_urls": ["https://www.youtube.com/watch?v=one"],
                "retrieval_method": "yt-dlp transcript",
                "runner_executed": True,
                "terminal_success": True,
                "evidence_retrieved": True,
            },
            {
                "source": "x",
                "status": "complete",
                "count": 4,
                "content_records": 4,
                "body_evidence_count": 4,
                "evidence_urls": ["https://x.com/example/status/one"],
                "retrieval_method": "read-only X runner",
                "runner_executed": True,
                "terminal_success": True,
                "evidence_retrieved": True,
            },
            {
                "source": "reddit",
                "status": "complete",
                "count": 4,
                "content_records": 4,
                "body_evidence_count": 4,
                "evidence_urls": ["https://www.reddit.com/r/example/comments/one/thread/"],
                "retrieval_method": "read-only Reddit runner",
                "runner_executed": True,
                "terminal_success": True,
                "evidence_retrieved": True,
            },
            {
                "source": "web",
                "status": "complete",
                "count": 4,
                "content_records": 4,
                "body_evidence_count": 4,
                "evidence_urls": ["https://example.com/article"],
                "retrieval_method": "ordinary Web page reader",
                "runner_executed": True,
                "terminal_success": True,
                "evidence_retrieved": True,
            },
        ]
        return {"sources": [record for record in records if record["source"] != missing]}

    def test_core4_validator_requires_each_media_and_terminal_proof(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            packet = work / "core4.json"
            packet.write_text(json.dumps(self.core4_packet()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_research_evidence.py"),
                    "--input", str(packet),
                    "--require-core-4",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            valid = json.loads(result.stdout)
            self.assertTrue(valid["valid"])
            self.assertEqual(valid["completion_contract"], "core4_strict_v1")
            self.assertEqual(valid["required_sources"], ["youtube", "x", "reddit", "web"])

            for missing in ("youtube", "x", "reddit", "web"):
                packet.write_text(json.dumps(self.core4_packet(missing)), encoding="utf-8")
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "validate_research_evidence.py"),
                        "--input", str(packet),
                        "--require-core-4",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 1, missing)
                invalid = json.loads(result.stdout)
                self.assertTrue(invalid["research_incomplete"])
                self.assertTrue(any(
                    blocker.get("source") == missing
                    and blocker.get("code") == "required_source_unsatisfied"
                    for blocker in invalid["blockers"]
                ))

            packet.write_text(json.dumps(self.core4_packet()), encoding="utf-8")
            payload = json.loads(packet.read_text(encoding="utf-8"))
            next(record for record in payload["sources"] if record["source"] == "x")["status"] = "partial"
            packet.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_research_evidence.py"),
                    "--input", str(packet),
                    "--require-core-4",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertTrue(any(
                blocker.get("source") == "x"
                and blocker.get("reason") == "terminal_failure"
                for blocker in json.loads(result.stdout)["blockers"]
            ))

    def test_standard_includes_optional_candidates_without_all_platform_wording(self):
        plan = self.run_plan("--question", "Geminiの使い方を調査して")
        self.assertEqual(plan["mode"], "standard")
        self.assertEqual(set(plan["source_selection"]["optional_candidates"]), {
            "tiktok", "instagram", "bluesky", "linkedin", "arxiv", "polymarket", "bilibili", "xiaohongshu",
            "facebook", "v2ex", "xiaoyuzhou", "xueqiu",
        })
        self.assertTrue(plan["source_selection"]["optional_candidates_included_by_default"])
        self.assertFalse(plan["source_selection"]["all_platform_wording_required"])
        self.assertEqual(plan["source_balance"]["optional_candidate_count"], 12)

    def test_standard_has_source_specific_collection_limits(self):
        plan = self.run_plan("--question", "Geminiの使い方を調査して")
        self.assertEqual(plan["collection_limits"]["youtube"]["items"], {"target": 5, "min": 3, "max": 10})
        self.assertEqual(plan["collection_limits"]["x"], {
            "primary_posts": {"target": 10, "min": 5, "max": 20},
            "replies": {"target": 20, "min": 10, "max": 40},
            "quoted_posts": {"target": 5, "min": 2, "max": 10},
        })
        self.assertEqual(plan["collection_limits"]["reddit"]["comments"], {"target": 20, "min": 10, "max": 40})
        self.assertEqual(plan["collection_limits"]["web"]["opened_pages"], {"target": 12, "min": 8, "max": 15})
        self.assertEqual(plan["collection_limits"]["tiktok"]["items"], {"target": 3, "min": 1, "max": 8})
        x_record = next(record for record in plan["sources"] if record["source"] == "x")
        self.assertEqual(x_record["collection_limits"], plan["collection_limits"]["x"])

    def test_quick_stays_narrow_and_seed_expansion_is_bounded(self):
        plan = self.run_plan(
            "https://www.youtube.com/watch?v=abc123",
            "--mode", "quick",
            "--question", "この動画の要点だけ",
        )
        self.assertEqual(plan["mode"], "quick")
        self.assertEqual([record["source"] for record in plan["sources"]], ["youtube", "x", "reddit", "web"])
        self.assertEqual(plan["source_selection"]["optional_candidates"], [])
        self.assertFalse(plan["source_selection"]["optional_candidates_included_by_default"])
        self.assertEqual(set(plan["collection_limits"]), {"youtube", "x", "reddit", "web"})
        self.assertEqual(plan["collection_limits"]["x"]["primary_posts"], {"target": 2, "min": 2, "max": 5})
        self.assertEqual(plan["collection_limits"]["reddit"]["submissions"], {"target": 2, "min": 2, "max": 5})

    def test_optional_seed_forces_its_source_with_bounded_quick_expansion(self):
        plan = self.run_plan(
            "https://www.v2ex.com/t/1234567",
            "--mode", "quick",
            "--question", "この投稿の要点だけ",
        )
        self.assertEqual(plan["seeds"][0]["type"], "v2ex")
        self.assertEqual([record["source"] for record in plan["sources"]], ["youtube", "x", "reddit", "web", "v2ex"])

    def test_canonical_source_identity_preserves_explicit_valid_values(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "raw.json"
            source.write_text(json.dumps([
                {"source": "hacker-news", "url": "https://unknown.example/item", "text": "one"},
                {"source": "instagram", "url": "https://unknown.example/item", "text": "two"},
                {"source": "x", "url": "https://www.youtube.com/watch?v=abc", "text": "three"},
            ]), encoding="utf-8")
            output = work / "evidence.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "normalize_evidence.py"), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["source"] for record in records], ["hacker_news", "instagram", "x"])

    def test_optional_host_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "raw.json"
            source.write_text(json.dumps([
                {"url": "https://www.bsky.app/profile/example", "text": "one"},
                {"url": "https://www.b23.tv/example", "text": "two"},
                {"url": "https://arxiv.org/abs/1234.5678", "text": "three"},
                {"url": "https://www.v2ex.com/t/1234567", "text": "four"},
                {"url": "https://www.xiaoyuzhoufm.com/episode/example", "text": "five"},
                {"url": "https://xueqiu.com/1234567890/123456789", "text": "six"},
            ]), encoding="utf-8")
            output = work / "evidence.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "normalize_evidence.py"), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([record["source"] for record in records], ["bluesky", "bilibili", "arxiv", "v2ex", "xiaoyuzhou", "xueqiu"])

    def test_unknown_host_falls_back_to_web(self):
        plan = self.run_plan("https://research.example.invalid/article", "--question", "このページを確認")
        self.assertEqual(plan["seeds"][0]["type"], "web")
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "raw.json"
            source.write_text(json.dumps({"url": "https://research.example.invalid/article", "text": "unknown host"}), encoding="utf-8")
            output = work / "evidence.jsonl"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "normalize_evidence.py"), "--input", str(source), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["source"], "web")

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

    def test_url_transcript_prefers_captions_and_falls_back_per_language(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            fake_ytdlp = work / "yt-dlp"
            fake_ytdlp.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "args = sys.argv\n"
                "language = args[args.index('--sub-langs') + 1]\n"
                "if language == 'ja':\n"
                "    raise SystemExit(1)\n"
                "output = args[args.index('--output') + 1]\n"
                "path = pathlib.Path(output.replace('%(id)s', 'abc123').replace('%(ext)s', language + '.vtt'))\n"
                "path.parent.mkdir(parents=True, exist_ok=True)\n"
                "path.write_text('WEBVTT\\n\\n00:00:01.000 --> 00:00:03.000\\nFallback subtitle.\\n', encoding='utf-8')\n",
                encoding="utf-8",
            )
            fake_ytdlp.chmod(0o755)
            agent_marker = work / "agent-reach-called"
            fake_agent = work / "agent-reach"
            fake_agent.write_text(
                "#!/usr/bin/env python3\n"
                f"import pathlib\npathlib.Path({str(agent_marker)!r}).write_text('called', encoding='utf-8')\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            fake_agent.chmod(0o755)
            output = work / "transcript"
            env = os.environ.copy()
            env["PATH"] = f"{work}:{env['PATH']}"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "extract_transcript.py"),
                    "https://www.youtube.com/watch?v=abc123",
                    "--out", str(output),
                    "--lang", "ja", "en",
                    "--backend", "auto",
                    "--timeout", "5",
                ],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["language"], "en")
            self.assertEqual(manifest["retrieval_method"], "yt_dlp")
            self.assertFalse(agent_marker.exists(), result.stderr)
            transcript = json.loads((output / "transcript.json").read_text(encoding="utf-8"))
            self.assertEqual(transcript[0]["text"], "Fallback subtitle.")

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

    def test_reddit_selftext_and_topic_metadata_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            source = work / "raw.json"
            source.write_text(
                json.dumps([
                    {
                        "source": "reddit",
                        "url": "https://www.reddit.com/r/codex/comments/abc/example/",
                        "title": "Codex Desktop automation",
                        "selftext": "I tested a scheduled Codex Desktop task.",
                        "topic_relevance": "relevant",
                        "relevance_reason": "Direct first-hand test of the requested feature.",
                    }
                ]),
                encoding="utf-8",
            )
            output = work / "evidence.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "normalize_evidence.py"),
                    "--input", str(source),
                    "--output", str(output),
                    "--topic", "Codex Desktop automation",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertEqual(record["text"], "I tested a scheduled Codex Desktop task.")
            self.assertIn("codex", record["matched_topic_terms"])
            self.assertEqual(record["topic_relevance"], "relevant")

    def test_topic_evidence_validator_requires_reviewed_body_content(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            evidence = work / "evidence.jsonl"
            records = [
                {"source": "x", "url": "https://x.com/a/status/1", "title": "Codex Desktop", "text": "I tested Codex Desktop automation.", "topic_relevance": "relevant", "relevance_reason": "Direct test."},
                {"source": "x", "url": "https://x.com/a/status/2", "title": "Codex", "text": "A scheduled automation task ran overnight.", "topic_relevance": "relevant", "relevance_reason": "Direct scheduled-task report."},
                {"source": "reddit", "url": "https://www.reddit.com/r/codex/comments/a/one/", "title": "Codex Desktop", "text": "Codex Desktop automation is useful.", "topic_relevance": "relevant", "relevance_reason": "Direct usage report."},
                {"source": "reddit", "url": "https://www.reddit.com/r/codex/comments/b/two/", "title": "Scheduled task", "text": "I ran an automation task with Codex.", "topic_relevance": "relevant", "relevance_reason": "Direct task report."},
            ]
            evidence.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_topic_evidence.py"),
                    "--input", str(evidence),
                    "--topic", "Codex Desktop automation",
                    "--keyword", "Codex",
                    "--keyword", "Desktop",
                    "--keyword", "automation",
                    "--require-source", "x",
                    "--require-source", "reddit",
                    "--min-relevant", "2",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)["valid"])

            records[-1]["text"] = ""
            records[-1].pop("topic_relevance")
            evidence.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_topic_evidence.py"),
                    "--input", str(evidence),
                    "--topic", "Codex Desktop automation",
                    "--keyword", "Codex",
                    "--keyword", "Desktop",
                    "--keyword", "automation",
                    "--require-source", "x",
                    "--require-source", "reddit",
                    "--min-relevant", "2",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            invalid = json.loads(result.stdout)
            self.assertTrue(any(item["code"] == "missing_source_content" for item in invalid["blockers"]))
            self.assertTrue(any(item["code"] == "relevance_unreviewed" for item in invalid["blockers"]))

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
            self.assertEqual(plan["youtube_policy"]["maximum_count"], 12)
            self.assertEqual(plan["collection_limits"]["x"]["primary_posts"]["target"], 20)
            self.assertEqual(plan["collection_limits"]["x"]["replies"]["max"], 80)
            self.assertEqual(plan["collection_limits"]["web"]["opened_pages"]["target"], 20)
            self.assertTrue(plan["source_balance"]["non_youtube_corroboration_required"])
            self.assertGreaterEqual(len(plan["source_balance"]["non_youtube_sources"]), 1)
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
            self.assertTrue({"tiktok", "bluesky", "arxiv", "bilibili", "facebook", "v2ex"}.issubset(sources))

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
        self.assertIn("agent_reach_status.py", text)
        self.assertIn("XやReddit", text)
        self.assertIn("Cookie、APIキー、トークンはチャットに貼らない", text)

    def test_report_display_contract_is_present(self):
        skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        template_text = (ROOT / "references" / "report-template.md").read_text(encoding="utf-8")
        self.assertIn("Report display contract", skill_text)
        self.assertIn("System language", skill_text)
        self.assertIn("--artifacts-dir work/youtube", skill_text)
        self.assertIn("あなた向けの判断", template_text)
        self.assertIn("YouTube字幕・台本素材", template_text)
        self.assertIn("媒体別の生の声と一次情報", template_text)

    def test_agent_reach_status_translates_upstream_locale_text(self):
        upstream = {
            "twitter": {
                "status": "warn",
                "name": "Twitter/X \u63a8\u6587",
                "message": "twitter-cli \u5df2\u5b89\u88c5\u4f46\u6ca1\u6709\u5b8c\u6574\u7684\u663e\u5f0f\u51ed\u636e。",
                "tier": 1,
                "backends": ["twitter-cli", "OpenCLI"],
                "active_backend": None,
            },
            "reddit": {
                "status": "warn",
                "name": "Reddit \u5e16\u5b50\u548c\u8bc4\u8bba",
                "message": "OpenCLI \u5df2\u5b89\u88c5\uff0c\u4f46\u672a\u68c0\u6d4b\u5230\u5df2\u8fde\u63a5\u7684\u6d4f\u89c8\u5668\u6269\u5c55。",
                "tier": 1,
                "backends": ["OpenCLI", "rdt-cli"],
                "active_backend": None,
            },
            "bilibili": {
                "status": "ok",
                "name": "B\u7ad9\u89c6\u9891\u3001\u5b57\u5e55\u548c\u641c\u7d22",
                "message": "B\u7ad9\u641c\u7d22 API \u53ef\u8fbe",
                "tier": 1,
                "backends": ["B\u7ad9\u641c\u7d22 API"],
                "active_backend": "B\u7ad9\u641c\u7d22 API",
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            fake = work / "agent-reach"
            serialized = json.dumps(upstream, ensure_ascii=False)
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                f"print({serialized!r})\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{work}{os.pathsep}{env.get('PATH', '')}"
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "agent_reach_status.py"), "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotRegex(result.stdout, r"[一-龯]")
            translated = json.loads(result.stdout)
            self.assertEqual(translated["sources"]["twitter"]["status"], "warn")
            self.assertEqual(translated["sources"]["twitter"]["name"], "Twitter/X posts")
            self.assertIn("OpenCLI is configured", translated["sources"]["twitter"]["message"])
            self.assertEqual(translated["sources"]["twitter"]["effective_status"], "configured_unverified")
            self.assertTrue(translated["sources"]["twitter"]["verification"]["read_only_probe"])
            self.assertEqual(translated["sources"]["reddit"]["effective_status"], "configured_unverified")
            self.assertEqual(translated["sources"]["bilibili"]["active_backend"], "Bilibili Search API")

    def test_live_source_probe_requires_real_source_urls_and_validator_blocks_plans(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            fake = work / "opencli"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "source = sys.argv[1]\n"
                "url = 'https://x.com/example/status/123' if source == 'twitter' else 'https://www.reddit.com/r/codex/comments/abc/example/'\n"
                "print(json.dumps([{'id': '1', 'url': url, 'text': 'Codex Desktop automation sample; must not be persisted'}]))\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            probe = work / "live-source-probe.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "live_source_probe.py"),
                    "--source", "x",
                    "--source", "reddit",
                    "--query", "Codex Desktop automation",
                    "--command", str(fake),
                    "--out", str(probe),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(probe.read_text(encoding="utf-8"))
            self.assertEqual([record["status"] for record in packet["sources"]], ["complete", "complete"])
            self.assertTrue(all(record["count"] == 1 for record in packet["sources"]))
            self.assertTrue(all(record["content_records"] == 1 for record in packet["sources"]))
            self.assertTrue(all(record["topic_match_candidates"] == 1 for record in packet["sources"]))
            self.assertTrue(all(record["evidence_urls"] for record in packet["sources"]))
            self.assertTrue(all(record["configured"] for record in packet["sources"]))
            self.assertTrue(all(record["smoke_attempted"] for record in packet["sources"]))
            self.assertTrue(all(record["smoke_result"] == "complete" for record in packet["sources"]))
            self.assertTrue(all(record["evidence_retrieved"] for record in packet["sources"]))
            self.assertTrue(all(record["fallback_attempted"] is False for record in packet["sources"]))
            self.assertEqual(packet["browser_policy"], {"window": "background", "site_session": "persistent", "keep_tab": True})
            self.assertNotIn("text", probe.read_text(encoding="utf-8"))

            validation = work / "validation.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_research_evidence.py"),
                    "--input", str(probe),
                    "--require-source", "x",
                    "--require-source", "reddit",
                    "--out", str(validation),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(validation.read_text(encoding="utf-8"))["valid"])

            planned = work / "planned.json"
            planned.write_text(json.dumps({"sources": [{"source": "x", "status": "planned", "count": 0}]}), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "validate_research_evidence.py"),
                    "--input", str(planned),
                    "--require-source", "x",
                    "--require-source", "reddit",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            invalid = json.loads(result.stdout)
            self.assertTrue(invalid["research_incomplete"])
            self.assertTrue(any(blocker["code"] == "planned_not_retrieved" for blocker in invalid["blockers"]))
            self.assertTrue(any(blocker["code"] == "required_source_missing" for blocker in invalid["blockers"]))

    def test_live_source_probe_uses_read_only_x_fallback_after_primary_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            primary = work / "opencli"
            primary.write_text("#!/usr/bin/python3\nraise SystemExit(1)\n", encoding="utf-8")
            primary.chmod(0o755)
            fallback = work / "twitter"
            fallback.write_text(
                "#!/usr/bin/python3\n"
                "import json, os, sys\n"
                "if os.environ.get('TWITTER_AUTH_TOKEN') != 'test-token' or os.environ.get('TWITTER_CT0') != 'test-ct0': sys.exit(2)\n"
                "print(json.dumps({'tweets': [{'url': 'https://x.com/example/status/456', 'text': 'Codex Desktop automation'}]}))\n",
                encoding="utf-8",
            )
            fallback.chmod(0o755)
            probe = work / "probe.json"
            env = os.environ.copy()
            env["PATH"] = f"{work}{os.pathsep}{env.get('PATH', '')}"
            env["TWITTER_AUTH_TOKEN"] = "test-token"
            env["TWITTER_CT0"] = "test-ct0"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "live_source_probe.py"),
                    "--source", "x",
                    "--query", "Codex Desktop automation",
                    "--command", str(primary),
                    "--out", str(probe),
                ],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            record = json.loads(probe.read_text(encoding="utf-8"))["sources"][0]
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["backend"], "twitter-cli")
            self.assertTrue(record["fallback_attempted"])
            self.assertEqual([item["status"] for item in record["attempts"]], ["error", "complete"])
            self.assertTrue(record["evidence_retrieved"])

    def test_youtube_candidates_do_not_count_as_usable_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            packet = work / "source-status.json"
            packet.write_text(
                json.dumps({
                    "sources": [{
                        "source": "youtube",
                        "status": "partial",
                        "count": 5,
                        "evidence_urls": ["https://www.youtube.com/watch?v=one"],
                        "reason": "字幕取得がタイムアウト",
                    }]
                }),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_research_evidence.py"), "--input", str(packet), "--require-source", "youtube"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            invalid = json.loads(result.stdout)
            self.assertTrue(any(item["code"] == "youtube_usable_count_missing" for item in invalid["blockers"]))

            packet.write_text(
                json.dumps({
                    "sources": [{
                        "source": "youtube",
                        "status": "partial",
                        "count": 5,
                        "usable_count": 0,
                        "evidence_urls": ["https://www.youtube.com/watch?v=one"],
                        "reason": "字幕取得がタイムアウト",
                    }]
                }),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_research_evidence.py"), "--input", str(packet), "--require-source", "youtube"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            invalid = json.loads(result.stdout)
            self.assertTrue(any(item["code"] == "youtube_usable_evidence_missing" for item in invalid["blockers"]))

            packet.write_text(
                json.dumps({
                    "sources": [{
                        "source": "youtube",
                        "status": "partial",
                        "count": 5,
                        "usable_count": 2,
                        "evidence_urls": [
                            "https://www.youtube.com/watch?v=one",
                            "https://www.youtube.com/watch?v=two",
                        ],
                        "reason": "一部字幕のみ取得",
                    }]
                }),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_research_evidence.py"), "--input", str(packet), "--require-source", "youtube"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_research_gate_fail_closes_when_x_or_reddit_has_no_live_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            fake = work / "opencli"
            fake.write_text("#!/usr/bin/python3\nprint('[]')\n", encoding="utf-8")
            fake.chmod(0o755)
            gate = work / "research-gate.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "research_gate.py"),
                    "--query", "Codex Desktop automation",
                    "--command", str(fake),
                    "--timeout", "2",
                    "--out", str(gate),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            packet = json.loads(gate.read_text(encoding="utf-8"))
            self.assertEqual(packet["status"], "research_incomplete")
            self.assertEqual([record["status"] for record in packet["sources"]], ["no_results", "no_results"])
            self.assertTrue(packet["validation"]["research_incomplete"])

    def test_save_report_refuses_invalid_validation_without_partial_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            report = work / "report.md"
            report.write_text("# Incomplete\n", encoding="utf-8")
            validation = work / "validation.json"
            validation.write_text(json.dumps({"valid": False, "research_incomplete": True}), encoding="utf-8")
            output = work / "reports" / "report.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "save_report.py"),
                    "--input", str(report),
                    "--topic", "invalid",
                    "--validation", str(validation),
                    "--output", str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())
            self.assertTrue(json.loads(result.stdout)["research_incomplete"])

    def test_save_report_refuses_legacy_validation_as_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            report = work / "report.md"
            report.write_text("# Legacy\n", encoding="utf-8")
            validation = work / "validation.json"
            validation.write_text(json.dumps({"valid": True, "research_incomplete": False}), encoding="utf-8")
            output = work / "reports" / "report.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "save_report.py"),
                    "--input", str(report),
                    "--topic", "legacy",
                    "--validation", str(validation),
                    "--output", str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

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
                        self.assertEqual(len(plan["query_families"]), 6)
                        self.assertEqual(
                            [record["source"] for record in plan["sources"][:4]],
                            ["youtube", "x", "reddit", "web"],
                        )
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
                            {"source": "youtube", "status": "complete", "count": 8, "usable_count": 3, "relevant_count": 3, "evidence_urls": ["https://www.youtube.com/watch?v=one"], "retrieval_method": "yt-dlp / 字幕", "reason": ""},
                            {"source": "x", "status": "complete", "count": 2, "relevant_count": 2, "evidence_urls": ["https://x.com/example/status/1", "https://x.com/example/status/2"], "retrieval_method": "OpenCLI read-only search", "reason": ""},
                            {"source": "reddit", "status": "complete", "count": 2, "relevant_count": 2, "evidence_urls": ["https://www.reddit.com/r/codex/comments/one/example/", "https://www.reddit.com/r/codex/comments/two/example/"], "retrieval_method": "OpenCLI read-only search", "reason": ""},
                            {"source": "web", "status": "complete", "count": 2, "relevant_count": 2, "evidence_urls": ["https://example.com/article"], "retrieval_method": "ordinary Web page reader", "reason": ""},
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
            self.assertIn("| YouTube | `complete` | 3 |", coverage_text)
            self.assertIn("| X | `complete` | 2 |", coverage_text)
            validation = work / "research-validation.json"
            validation.write_text(
                json.dumps({
                    "valid": True,
                    "research_incomplete": False,
                    "completion_contract": "core4_strict_v1",
                    "required_sources": ["youtube", "x", "reddit", "web"],
                }),
                encoding="utf-8",
            )

            report = work / "final-report.md"
            report.write_text("## Conclusion\nテスト結果\n", encoding="utf-8")
            artifacts = work / "youtube" / "abc123"
            artifacts.mkdir(parents=True)
            (artifacts / "transcript.json").write_text("[]\n", encoding="utf-8")
            (artifacts / "chunks.json").write_text("[]\n", encoding="utf-8")
            (artifacts / "ignored.bin").write_bytes(b"ignored")
            report_dir = work / "reports"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "save_report.py"),
                    "--input",
                    str(report),
                    "--coverage",
                    str(coverage),
                    "--artifacts-dir",
                    str(work / "youtube"),
                    "--validation",
                    str(validation),
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
            saved_result = json.loads(result.stdout)
            self.assertFalse(saved_result["research_incomplete"])
            saved = saved_result["path"]
            saved_path = Path(saved)
            self.assertEqual(saved_path.name, "report.md")
            self.assertEqual(saved_path.parent.parent, report_dir.resolve())
            self.assertTrue(saved_path.exists())
            self.assertTrue(saved_path.read_text(encoding="utf-8").startswith("## 調査状況"))
            artifacts_path = Path(saved_result["artifacts_path"])
            self.assertEqual(artifacts_path, saved_path.parent / "artifacts")
            self.assertTrue((artifacts_path / "youtube" / "abc123" / "transcript.json").exists())
            self.assertFalse((artifacts_path / "youtube" / "abc123" / "ignored.bin").exists())


if __name__ == "__main__":
    unittest.main()
