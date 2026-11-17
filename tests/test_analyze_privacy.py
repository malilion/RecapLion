"""Public reports retain private activity without exposing repository details."""
import importlib.util
import copy
import json
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "analyze", ROOT / "skills/github-year-review/scripts/analyze.py"
)
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)
sys.path.insert(0, str(ROOT / "skills/github-year-review/scripts"))
import render


class PublicReportPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "examples/sample/raw.json").read_text())

    def test_private_activity_is_counted_without_publishing_repository_metadata(self):
        full = analyze.build(self.raw, exclude_private=False)
        private = [p for p in full["projects"] if p["is_private"]]
        self.assertTrue(private)
        public = analyze.build(self.raw, exclude_private=True)
        self.assertEqual(public["stats"], full["stats"])
        self.assertEqual(public["calendar"], full["calendar"])
        self.assertEqual(public["achievements"], full["achievements"])
        self.assertEqual(public["stats"]["private_commits"], sum(p["commits"] for p in private))
        self.assertFalse(any(p["is_private"] for p in public["projects"]))
        private_ids = {p["id"] for p in private}
        self.assertFalse(private_ids & set(public["commit_messages"]))
        self.assertEqual(public["commit_messages"],
                         {k: v for k, v in full["commit_messages"].items() if k not in private_ids})
        self.assertEqual(public["external_prs"], [])
        serialized = json.dumps(public)
        for p in private:
            self.assertNotIn(p["id"], serialized)
            self.assertNotIn(p["name"], serialized)

    def test_private_topics_release_tags_and_descriptions_are_not_serialized(self):
        def tag_private(value):
            if isinstance(value, dict):
                if value.get("isPrivate"):
                    value["description"] = "PRIVATE_DESCRIPTION_CANARY"
                    value["repositoryTopics"] = {"nodes": [{"topic": {"name": "PRIVATE_TOPIC_CANARY"}}]}
                    value["releases"] = {"nodes": [{
                        "tagName": "PRIVATE_RELEASE_CANARY", "name": "PRIVATE_RELEASE_NAME_CANARY",
                        "publishedAt": "2026-06-01T00:00:00Z",
                    }]}
                for nested in value.values():
                    tag_private(nested)
            elif isinstance(value, list):
                for nested in value:
                    tag_private(nested)

        tag_private(self.raw)
        public = analyze.build(self.raw, exclude_private=True)
        self.assertNotIn("CANARY", json.dumps(public))
        self.assertIn("CANARY", json.dumps(analyze.build(self.raw, exclude_private=False)))

    def test_unused_private_project_notes_are_not_embedded_in_public_html(self):
        full = analyze.build(self.raw, exclude_private=False)
        secret = next(p for p in full["projects"] if p["is_private"])
        public = analyze.build(self.raw, exclude_private=True)
        public["narrative"] = {
            "projects": {secret["id"]: {"tagline": "PRIVATE_NOTE_CANARY"}},
            "project_order": [secret["id"]],
        }
        output = render.render_html(public, "en")
        self.assertNotIn(secret["id"], output)
        self.assertNotIn("PRIVATE_NOTE_CANARY", output)

    def test_inventory_does_not_count_repositories_created_after_the_requested_range(self):
        future = copy.deepcopy(self.raw["owned_repositories"]["nodes"][0])
        future["nameWithOwner"] = "demo-dev/future-project"
        future["name"] = "future-project"
        future["createdAt"] = "2030-01-01T00:00:00Z"
        self.raw["owned_repositories"]["nodes"].append(future)
        report = analyze.build(self.raw, exclude_private=False)
        self.assertNotIn(future["nameWithOwner"], [p["id"] for p in report["projects"]])


if __name__ == "__main__":
    unittest.main()
