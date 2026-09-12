"""Unit tests for everything that doesn't require live network access:
schema, cleaning, normalization, dedupe, classification, relationships,
validation, and each source's pure parse() function against a realistic
sample payload. Run with:  python -m pytest tests/  (or just `python -m unittest`)
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.schema import make_id, make_entity
from src.pipeline.normalize_urls import normalize_url
from src.pipeline.dedupe import canonical_name, canonical_domain, dedupe
from src.pipeline.clean import clean_text, clean_entity
from src.pipeline.validate import validate_entity, validate_all
from src.pipeline.classify import tag_tasks, tag_recency, materialize_task_entities
from src.pipeline.relationships import build_relationships
from src.sources import github_source, huggingface_source, youtube_source, rss_source


class TestNormalizeUrls(unittest.TestCase):
    def test_adds_https(self):
        self.assertEqual(normalize_url("example.com"), "https://example.com")

    def test_strips_utm_but_keeps_other_params(self):
        out = normalize_url("https://example.com/page?utm_source=x&keep=1")
        self.assertIn("keep=1", out)
        self.assertNotIn("utm_source", out)

    def test_strips_trailing_slash(self):
        self.assertEqual(normalize_url("https://example.com/"), "https://example.com")

    def test_empty_url_stays_empty(self):
        self.assertEqual(normalize_url(""), "")


class TestDedupe(unittest.TestCase):
    def test_canonical_name_merges_variants(self):
        self.assertEqual(canonical_name("OpenAI Inc"), canonical_name("Open AI"))

    def test_canonical_domain_ignores_www_and_path(self):
        self.assertEqual(canonical_domain("https://www.openai.com/blog"), canonical_domain("https://openai.com/"))

    def test_dedupe_removes_duplicate_by_domain_and_keeps_richer_description(self):
        e1 = make_entity("company", "OpenAI", "short", "https://openai.com", ["Companies"], "seed", "")
        e2 = make_entity("company", "OpenAI", "a longer, richer description", "https://openai.com/", ["Companies"], "seed", "")
        out = dedupe([e1, e2])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["description"], "a longer, richer description")

    def test_dedupe_does_not_collapse_unrelated_empty_url_entities(self):
        e1 = make_entity("task", "Code Generation", "d1", "", ["Tasks"], "taxonomy", "")
        e2 = make_entity("task", "Image Generation", "d2", "", ["Tasks"], "taxonomy", "")
        out = dedupe([e1, e2])
        self.assertEqual(len(out), 2)


class TestSchema(unittest.TestCase):
    def test_id_is_deterministic(self):
        id1 = make_id("model", "Org/Model", "https://huggingface.co/Org/Model")
        id2 = make_id("model", "Org/Model", "https://huggingface.co/Org/Model")
        self.assertEqual(id1, id2)

    def test_id_differs_for_different_entities(self):
        id1 = make_id("model", "Org/Model", "https://huggingface.co/Org/Model")
        id2 = make_id("model", "Org/OtherModel", "https://huggingface.co/Org/OtherModel")
        self.assertNotEqual(id1, id2)


class TestCleanText(unittest.TestCase):
    def test_strips_html_and_collapses_whitespace(self):
        self.assertEqual(clean_text("<p>Hello   world</p>"), "Hello world")

    def test_unescapes_html_entities(self):
        self.assertEqual(clean_text("Tom &amp; Jerry"), "Tom & Jerry")


class TestValidate(unittest.TestCase):
    def test_missing_url_flagged_for_model(self):
        e = make_entity("model", "Test Model", "desc", "", ["Models"], "hf", "")
        self.assertIn("missing url", validate_entity(e))

    def test_task_entity_does_not_require_url(self):
        e = make_entity("task", "Code Generation", "desc", "", ["Tasks"], "taxonomy", "")
        self.assertNotIn("missing url", validate_entity(e))

    def test_missing_description_flagged(self):
        e = make_entity("tool", "X", "", "https://x.com", ["Tools"], "seed", "")
        self.assertIn("missing description", validate_entity(e))

    def test_validate_all_splits_valid_and_invalid(self):
        good = make_entity("tool", "Good", "a real tool", "https://good.com", ["Tools"], "seed", "")
        bad = make_entity("tool", "Bad", "", "", ["Tools"], "seed", "")
        clean, report = validate_all([good, bad])
        self.assertEqual(len(clean), 1)
        self.assertEqual(report["valid"], 1)
        self.assertEqual(report["invalid"], 1)


class TestClassify(unittest.TestCase):
    def test_tag_tasks_matches_keyword_in_description(self):
        e = make_entity("model", "Test", "a tool for code generation and programming", "https://x.com", [], "s", "")
        tag_tasks(e)
        self.assertIn("code-generation", e["metadata"].get("related_tasks", []))

    def test_tag_recency_marks_new_for_recent_date(self):
        import datetime as dt
        e = make_entity("repository", "Test", "d", "https://x.com", [], "s", "")
        e["metadata"]["pushed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        tag_recency(e)
        self.assertIn("New", e["categories"])

    def test_tag_recency_ignores_old_date(self):
        e = make_entity("repository", "Test", "d", "https://x.com", [], "s", "")
        e["metadata"]["pushed_at"] = "2015-01-01T00:00:00Z"
        tag_recency(e)
        self.assertNotIn("New", e["categories"])

    def test_materialize_task_entities_returns_nonempty_list(self):
        tasks = materialize_task_entities()
        self.assertTrue(len(tasks) > 0)
        self.assertTrue(all(t["entity_type"] == "task" for t in tasks))


class TestRelationships(unittest.TestCase):
    def test_company_develops_repository_by_owner_match(self):
        company = make_entity("company", "Anthropic", "d", "https://anthropic.com", ["Companies"], "seed", "")
        repo = make_entity("repository", "anthropics/courses", "d", "https://github.com/anthropics/courses",
                            ["Repositories"], "GitHub", "https://github.com/anthropics/courses",
                            metadata={"owner": "anthropics"})
        rels = build_relationships([company, repo])
        self.assertTrue(any(r["relation"] == "develops" and r["to"] == repo["id"] for r in rels))

    def test_company_develops_seed_tool_by_maker_field(self):
        company = make_entity("company", "Anthropic", "d", "https://anthropic.com", ["Companies"], "seed", "")
        tool = make_entity("tool", "Claude", "d", "https://claude.ai", ["Tools"], "seed", "",
                            metadata={"maker": "Anthropic"})
        rels = build_relationships([company, tool])
        self.assertTrue(any(r["relation"] == "develops" and r["to"] == tool["id"] for r in rels))

    def test_tool_solves_task_relationship(self):
        task = materialize_task_entities()
        tool = make_entity("tool", "CodeHelper", "an assistant for code generation", "https://x.com", ["Tools"], "seed", "")
        tag_tasks(tool)
        rels = build_relationships([tool] + task)
        self.assertTrue(any(r["relation"] == "solves" and r["from"] == tool["id"] for r in rels))


class TestGithubParse(unittest.TestCase):
    def test_prefers_homepage_over_html_url(self):
        item = {
            "full_name": "acme/tool", "name": "tool", "description": "A tool.",
            "html_url": "https://github.com/acme/tool", "homepage": "https://acme.dev",
            "stargazers_count": 120, "language": "Python", "pushed_at": "2026-08-01T00:00:00Z",
            "topics": ["ai"], "owner": {"login": "acme", "avatar_url": "https://x/a.png"}, "license": None,
        }
        e = github_source.parse(item, "repository", [])
        self.assertEqual(e["url"], "https://acme.dev")
        self.assertEqual(e["metadata"]["stars"], 120)
        self.assertEqual(e["metadata"]["owner"], "acme")

    def test_falls_back_to_html_url_when_no_homepage(self):
        item = {"full_name": "acme/tool2", "html_url": "https://github.com/acme/tool2", "homepage": "",
                "owner": {"login": "acme"}}
        e = github_source.parse(item, "repository", [])
        self.assertEqual(e["url"], "https://github.com/acme/tool2")


class TestHFParse(unittest.TestCase):
    def test_extracts_license_from_tags_and_provider_from_id(self):
        item = {"id": "acme/model", "pipeline_tag": "text-generation",
                "tags": ["license:apache-2.0", "pytorch"], "downloads": 500, "likes": 10,
                "lastModified": "2026-07-01"}
        e = huggingface_source.parse(item, "model", [])
        self.assertEqual(e["metadata"]["license"], "apache-2.0")
        self.assertEqual(e["metadata"]["provider"], "acme")
        self.assertEqual(e["url"], "https://huggingface.co/acme/model")


class TestYoutubeParse(unittest.TestCase):
    def test_builds_watch_url_from_video_id(self):
        item = {"id": {"videoId": "abc123"},
                "snippet": {"title": "T", "description": "D", "channelTitle": "C",
                            "publishedAt": "2026-01-01T00:00:00Z",
                            "thumbnails": {"high": {"url": "https://x/t.jpg"}}}}
        e = youtube_source.parse(item, "video", [])
        self.assertEqual(e["url"], "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(e["metadata"]["channel"], "C")


class TestRssParse(unittest.TestCase):
    def test_parse_maps_entry_fields(self):
        entry = {"title": "Big AI Launch", "summary": "<p>Some <b>html</b>.</p>",
                  "link": "https://example.com/a", "published": "2026-09-01T00:00:00Z"}
        e = rss_source.parse("Example Feed", "https://example.com/rss", entry)
        self.assertEqual(e["url"], "https://example.com/a")
        self.assertEqual(e["source"]["name"], "Example Feed")


class TestPolicyAndRelationshipQuality(unittest.TestCase):
    def test_third_party_url_rejection_is_detected(self):
        bad = make_entity("company", "Example", "desc", "https://www.crunchbase.com/org/example", ["Companies"], "seed", "")
        issues = validate_entity(bad)
        self.assertIn("third-party url", issues)

    def test_duplicate_relationships_are_not_re_emitted(self):
        company = make_entity("company", "Anthropic", "desc", "https://anthropic.com", ["Companies"], "seed", "")
        repo = make_entity("repository", "anthropics/courses", "desc", "https://github.com/anthropics/courses", ["Repositories"], "GitHub", "https://github.com/anthropics/courses", metadata={"owner": "anthropics"})
        rels = build_relationships([company, repo])
        deduped = {(r["from"], r["relation"], r["to"]) for r in rels}
        self.assertEqual(len(rels), len(deduped))

    def test_relationships_reject_self_reference(self):
        company = make_entity("company", "Anthropic", "desc", "https://anthropic.com", ["Companies"], "seed", "")
        rels = build_relationships([company])
        self.assertFalse(any(r["from"] == r["to"] for r in rels))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDescribeWithMockedLLM(unittest.TestCase):
    """Confirms the describe-step contract: the Gemini adapter passes the
    request through a Google SDK-shaped client object and falls back to the
    source description if the response body is empty or the request fails.
    This is intentionally mocked at the SDK call boundary only."""

    def test_mocked_llm_fills_blank_description_and_then_validates(self):
        from unittest.mock import MagicMock
        from src.pipeline import describe

        entity = make_entity("company", "OpenAI", "A research and product company.", "https://openai.com", ["Companies"], "seed", "")
        self.assertNotIn("missing description", validate_entity(entity))

        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.text = "An AI research and product company known for GPT and ChatGPT."
        fake_client.models.generate_content.return_value = fake_response

        result = describe._describe_one(fake_client, entity)
        self.assertIn("AI research", result)

    def test_gemini_quota_error_parser_handles_retry_delay_and_graceful_source_desc(self):
        from unittest.mock import MagicMock
        from src.pipeline import describe

        class FakeAPIError(Exception):
            def __init__(self):
                self.code = 429
                self.status = "RESOURCE_EXHAUSTED"
                self.details = {
                    "error": {
                        "code": 429,
                        "message": "You exceeded your current quota.",
                        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "51s"}],
                    }
                }
                super().__init__("429 RESOURCE_EXHAUSTED. " + str(self.details))

        entity = make_entity("company", "OpenAI", "AI research and product company.", "https://openai.com", ["Companies"], "seed", "")
        exc = FakeAPIError()
        delay = describe._extract_retry_delay_from_error(exc)
        self.assertEqual(delay, 51.0)
        self.assertTrue(describe._is_gemini_resource_exhausted(exc))

        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = exc
        self.assertEqual(describe._describe_one(fake_client, entity), entity['description'])
