"""--scope public must never include private activity, not even as anonymous counts."""
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/github-year-review/scripts"
sys.path.insert(0, str(SCRIPTS))
import public_source as public  # noqa: E402
import fetch_github_year as fetch  # noqa: E402
import recap  # noqa: E402

START = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)


def repo(name, private=False):
    return {"nameWithOwner": f"demo/{name}", "name": name, "isPrivate": private, "isFork": False,
            "createdAt": "2026-01-05T00:00:00Z", "stargazerCount": 3}


def page(nodes, following=None):
    return {"nodes": nodes, "pageInfo": {"hasNextPage": following is not None, "endCursor": following}}


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.pub, self.sec = repo("open"), repo("secret", private=True)

    def __call__(self, document, variables):
        self.calls.append((document, dict(variables)))
        if document == public.PROFILE_QUERY:
            return {"user": {"login": "demo", "name": "Demo"}}
        if document == public.COMMITS_QUERY:
            month = variables["from"][:7]
            rows = [
                {"repository": {"nameWithOwner": "demo/open", "isPrivate": False},
                 "contributions": {"totalCount": 1, "nodes": [{"occurredAt": f"{month}-03T00:00:00Z", "commitCount": 4}]}},
                {"repository": {"nameWithOwner": "demo/secret", "isPrivate": True},
                 "contributions": {"totalCount": 1, "nodes": [{"occurredAt": f"{month}-04T00:00:00Z", "commitCount": 50}]}},
            ]
            return {"user": {"contributionsCollection": {"commitContributionsByRepository": rows}}}
        for field in public.EVENTS:
            if f"{field}(first:100" in document:
                after = variables.get("after")
                if field == "pullRequestContributions":
                    nodes = ([{"occurredAt": "2026-01-10T12:00:00Z", "pullRequest": {"repository": self.pub}},
                              {"occurredAt": "2026-01-11T12:00:00Z", "pullRequest": {"repository": self.sec}}]
                             if after is None else
                             [{"occurredAt": "2026-02-10T12:00:00Z", "pullRequest": {"repository": self.pub}}])
                    conn = page(nodes, "p2" if after is None else None)
                elif field == "issueContributions":
                    conn = page([{"occurredAt": "2026-01-12T12:00:00Z", "issue": {"repository": self.sec}}])
                elif field == "pullRequestReviewContributions":
                    conn = page([{"occurredAt": "2026-01-13T12:00:00Z", "repository": self.pub}])
                else:
                    conn = page([{"occurredAt": "2026-01-05T00:00:00Z", "repository": self.pub},
                                 {"occurredAt": "2026-01-06T00:00:00Z", "repository": self.sec}])
                return {"user": {"contributionsCollection": {field: conn}}}
        if "privacy:PUBLIC" in document:
            return {"user": {"repositories": page([self.pub])}}
        if "search(" in document or "merged:" in json.dumps(variables):
            return {"merged": {"issueCount": 2}, "mergedExternal": {"issueCount": 0, "nodes": []},
                    "issuesClosed": {"issueCount": 0}, "prsOpened": {"issueCount": 2}}
        raise AssertionError(f"unexpected query: {document[:80]}")


class PublicScopeTests(unittest.TestCase):
    def collect(self, gh=None):
        gh = gh or FakeGitHub()
        raw = public.collect("demo", START, END, "UTC", gh, "nameWithOwner isPrivate",
                             "query{search(merged:$merged)}", lambda *_: None)
        return raw, gh

    def test_private_activity_is_left_out_everywhere(self):
        raw, _ = self.collect()
        cc = raw["contributions"]
        # public: 2 months x 4 commits + 2 PRs + 1 review + 1 repo created
        self.assertEqual(cc["contributionCalendar"]["totalContributions"], 12)
        self.assertEqual(cc["totalCommitContributions"], 8)
        self.assertEqual(cc["totalPullRequestContributions"], 2)
        self.assertEqual(cc["totalIssueContributions"], 0)
        self.assertEqual(cc["totalPullRequestReviewContributions"], 1)
        self.assertEqual(cc["totalRepositoryContributions"], 1)
        self.assertEqual(cc["restrictedContributionsCount"], 0)
        self.assertNotIn("secret", json.dumps(raw))

    def test_calendar_days(self):
        raw, _ = self.collect()
        days = {d["date"]: d["contributionCount"]
                for w in raw["contributions"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]}
        self.assertEqual(days["2026-01-03"], 4)
        self.assertEqual(days["2026-01-04"], 0)   # private commits
        self.assertEqual(days["2026-01-11"], 0)   # private PR
        self.assertEqual(days["2026-02-10"], 1)   # second page of PRs
        self.assertEqual(min(days), "2026-01-01")
        self.assertEqual(max(days), "2026-02-28")

    def test_commits_are_read_month_by_month(self):
        _, gh = self.collect()
        months = [v["from"][:7] for d, v in gh.calls if d == public.COMMITS_QUERY]
        self.assertEqual(months, ["2026-01", "2026-02"])

    def test_searches_are_public_only(self):
        _, gh = self.collect()
        searches = [v for d, v in gh.calls if "merged" in v]
        self.assertTrue(searches)
        for query in searches[0].values():
            self.assertIn("is:public", query)

    def test_busy_month_is_split(self):
        gh = FakeGitHub()
        busy = [{"repository": {"nameWithOwner": f"demo/r{i}", "isPrivate": False},
                 "contributions": {"totalCount": 0, "nodes": []}} for i in range(100)]
        original = gh.__call__
        windows = []

        def call(document, variables):
            if document == public.COMMITS_QUERY:
                windows.append((variables["from"], variables["to"]))
                if len(windows) == 1:
                    return {"user": {"contributionsCollection": {"commitContributionsByRepository": busy}}}
            return original(document, variables)

        public.collect("demo", START, dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc), "UTC", call,
                       "nameWithOwner", "q", lambda *_: None)
        self.assertGreater(len(windows), 2)


class ScopeChoiceTests(unittest.TestCase):
    def test_no_terminal_defaults_to_public(self):
        with patch.object(sys.stdin, "isatty", return_value=False), patch("sys.stderr", io.StringIO()):
            self.assertEqual(recap.ask_scope(), "public")

    def test_terminal_choice(self):
        with patch.object(sys.stdin, "isatty", return_value=True), patch("sys.stderr", io.StringIO()), \
                patch("builtins.input", side_effect=["x", "2"]):
            self.assertEqual(recap.ask_scope(), "all")

    def test_public_run_refuses_a_private_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "raw.json").write_text(json.dumps({"meta": {"scope": "all", "user": "demo", "year": 2026}}))
            argv = ["recap.py", "--user", "demo", "--year", "2026", "--out", tmp, "--skip-fetch", "--scope", "public"]
            with patch.object(sys, "argv", argv), patch("sys.stderr", io.StringIO()):
                with self.assertRaises(SystemExit):
                    recap.main()

    def test_fetch_scope_flags_conflict(self):
        argv = ["fetch_github_year.py", "--user", "demo", "--scope", "public", "--include-private"]
        with patch.object(sys, "argv", argv), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                fetch.main()


if __name__ == "__main__":
    unittest.main()
