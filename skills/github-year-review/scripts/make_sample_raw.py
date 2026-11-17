#!/usr/bin/env python3
"""Generate a fictional raw.json so the pipeline can be tried without a GitHub token.

  python3 scripts/make_sample_raw.py -o raw.json
"""
import argparse
import datetime as dt
import json
import os
import random

random.seed(2026)
YEAR = 2026
LOGIN = "demo-dev"


def repo(name, desc, lang, color, stars, created, topics, langs, releases=0, private=False):
    return {
        "nameWithOwner": f"{LOGIN}/{name}", "name": name, "description": desc,
        "url": f"https://github.com/{LOGIN}/{name}", "homepageUrl": None,
        "stargazerCount": stars, "forkCount": stars // 8, "isPrivate": private, "isFork": False, "isArchived": False,
        "createdAt": created, "pushedAt": f"{YEAR}-11-10T10:00:00Z", "owner": {"login": LOGIN},
        "primaryLanguage": {"name": lang, "color": color},
        "repositoryTopics": {"nodes": [{"topic": {"name": t}} for t in topics]},
        "languages": {"totalSize": sum(s for _, _, s in langs),
                      "edges": [{"size": s, "node": {"name": n, "color": c}} for n, c, s in langs]},
        "releases": {"totalCount": releases, "nodes": [
            {"tagName": f"v1.{i}.0", "name": f"v1.{i}.0", "publishedAt": f"{YEAR}-{min(12, 3 + i * 2):02d}-15T00:00:00Z"}
            for i in range(releases)]},
    }


REPOS = [
    (repo("agent-forge", "A multi-agent orchestration framework with tool sandboxing", "TypeScript", "#3178c6", 412,
          f"{YEAR}-02-03T00:00:00Z", ["ai", "agents", "llm"],
          [("TypeScript", "#3178c6", 800), ("Python", "#3572A5", 120), ("Shell", "#89e051", 10)], releases=4), 486),
    (repo("rust-kv", "Embedded LSM-tree key-value store written in Rust", "Rust", "#dea584", 156,
          f"{YEAR}-05-20T00:00:00Z", ["database", "rust", "storage"], [("Rust", "#dea584", 900)], releases=2), 233),
    (repo("homelab-dash", "Self-hosted dashboard for home servers", "Go", "#00ADD8", 38,
          f"{YEAR}-08-11T00:00:00Z", ["homelab", "dashboard"],
          [("Go", "#00ADD8", 500), ("Vue", "#41b883", 300), ("CSS", "#563d7c", 60)]), 141),
    (repo("invoice-saas", "Invoicing SaaS for freelancers", "Python", "#3572A5", 0,
          "2025-06-01T00:00:00Z", [], [("Python", "#3572A5", 600), ("HTML", "#e34c26", 150)], private=True), 118),
    (repo("dotfiles", "My dev environment", "Lua", "#000080", 12,
          "2021-01-01T00:00:00Z", ["neovim"], [("Lua", "#000080", 100), ("Shell", "#89e051", 40)]), 37),
    (repo("kotlin-habit", "Minimal habit tracker for Android", "Kotlin", "#A97BFF", 21,
          f"{YEAR}-10-02T00:00:00Z", ["android", "compose"], [("Kotlin", "#A97BFF", 400)]), 29),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", default="raw.json")
    args = ap.parse_args()

    start = dt.date(YEAR, 1, 1)
    end = dt.date(YEAR, 11, 17)
    weeks, week, total = [], [], 0
    d = start
    while d <= end:
        wd = (d.weekday() + 1) % 7
        busy = 1.4 if d.month in (3, 4, 9, 10) else 1.0
        if 6 <= d.month <= 7 and d.day >= 20:  # summer streak
            c = random.randint(2, 9)
        elif random.random() < (0.18 if wd in (0, 6) else 0.1):
            c = 0
        else:
            c = int(random.expovariate(1 / (4.5 * busy)))
        if d == dt.date(YEAR, 4, 12):
            c = 47
        week.append({"date": d.isoformat(), "contributionCount": c, "weekday": wd})
        total += c
        if wd == 6:
            weeks.append({"contributionDays": week})
            week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})

    msgs = ["feat: add tool sandbox", "fix: race in scheduler", "refactor: split planner module",
            "docs: update README", "perf: cache embeddings", "feat: compaction worker", "test: add fuzz tests",
            "chore: bump deps", "feat: SSE streaming", "fix: off-by-one in WAL replay"]
    samples = []
    for r, commits in REPOS[:4]:
        cs = []
        for _ in range(min(commits, 120)):
            hour = random.choice([1, 2, 10, 14, 15, 21, 22, 23, 23, 0, 16, 11])
            day = start + dt.timedelta(days=random.randint(0, (end - start).days))
            t = dt.datetime(day.year, day.month, day.day, hour, random.randint(0, 59), tzinfo=dt.timezone.utc)
            t -= dt.timedelta(hours=8)  # store as UTC for an Asia/Taipei user
            cs.append({"date": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "message": random.choice(msgs)})
        samples.append({"repository": r["nameWithOwner"], "commits": cs})

    raw = {
        "profile": {"login": LOGIN, "name": "Demo Dev", "avatarUrl": None, "bio": "Building tools for builders",
                    "url": f"https://github.com/{LOGIN}", "company": None, "location": "Taipei",
                    "createdAt": "2018-03-01T00:00:00Z", "followers": {"totalCount": 230}, "following": {"totalCount": 80}},
        "contributions": {
            "totalCommitContributions": sum(c for _, c in REPOS),
            "totalIssueContributions": 34, "totalPullRequestContributions": 71,
            "totalPullRequestReviewContributions": 58, "totalRepositoryContributions": 4,
            "totalRepositoriesWithContributedCommits": len(REPOS), "restrictedContributionsCount": 118,
            "contributionCalendar": {"totalContributions": total, "weeks": weeks},
            "commitContributionsByRepository": [{"contributions": {"totalCount": c}, "repository": r} for r, c in REPOS],
            "pullRequestContributionsByRepository": [], "issueContributionsByRepository": [],
            "pullRequestReviewContributionsByRepository": [],
        },
        "owned_repositories": {"totalCount": len(REPOS), "nodes": [r for r, _ in REPOS]},
        "search": {"merged": {"issueCount": 63}, "issuesClosed": {"issueCount": 20}, "prsOpened": {"issueCount": 71},
                   "mergedExternal": {"issueCount": 7, "nodes": [
                       {"title": "Fix memory leak in stream parser", "url": "https://github.com/example/parser/pull/1",
                        "mergedAt": f"{YEAR}-03-02T00:00:00Z", "repository": {"nameWithOwner": "example/parser", "stargazerCount": 5400}}]}},
        "commit_samples": samples,
        "meta": {"user": LOGIN, "year": YEAR, "tz": "Asia/Taipei", "source": "sample",
                 "range": {"from": f"{YEAR}-01-01T00:00:00Z", "to": f"{YEAR}-11-17T00:00:00Z"},
                 "generated_at": f"{YEAR}-11-17T00:00:00Z"},
    }
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
