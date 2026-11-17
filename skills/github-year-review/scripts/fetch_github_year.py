#!/usr/bin/env python3
"""Fetch one year of GitHub activity for a user and save it as raw JSON.

Only the Python standard library is used.

Auth (first match wins):
  1. --token
  2. env GITHUB_TOKEN / GH_TOKEN
  3. `gh auth token` (GitHub CLI)

With a token the GraphQL API is used (full contribution calendar, PR/issue/review
counts, private contribution counts). Without a token a limited public REST
fallback is used (60 requests/hour, calendar approximated from commits).

Usage:
  python3 fetch_github_year.py --user octocat --year 2026 --tz Asia/Taipei -o raw.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
UA = "github-year-review-skill"


# ---------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(f"[fetch] {msg}", file=sys.stderr)


def get_token(cli_token: str | None) -> str | None:
    if cli_token:
        return cli_token
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def request(url: str, token: str | None, body: dict | None = None) -> tuple[object, dict]:
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode() or "null"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} for {url}: {detail}") from None


def graphql(query: str, variables: dict, token: str) -> dict:
    data, _ = request(f"{API}/graphql", token, {"query": query, "variables": variables})
    if data.get("errors"):
        msgs = "; ".join(err.get("message", "?") for err in data["errors"])
        # Partial data is still useful (e.g. a search alias failing)
        if not data.get("data"):
            raise RuntimeError(f"GraphQL error: {msgs}")
        log(f"GraphQL warning: {msgs}")
    return data["data"]


# ---------------------------------------------------------------- GraphQL path
REPO_FIELDS = """
  nameWithOwner name description url homepageUrl stargazerCount forkCount
  isPrivate isFork isArchived createdAt pushedAt
  owner { login }
  primaryLanguage { name color }
  repositoryTopics(first: 8) { nodes { topic { name } } }
  languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
    totalSize edges { size node { name color } }
  }
  releases(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
    totalCount nodes { tagName name publishedAt }
  }
"""

MAIN_QUERY = f"""
query($login: String!, $from: DateTime!, $to: DateTime!) {{
  user(login: $login) {{
    login name avatarUrl bio url company location createdAt
    followers {{ totalCount }}
    following {{ totalCount }}
    contributionsCollection(from: $from, to: $to) {{
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      totalRepositoriesWithContributedCommits
      restrictedContributionsCount
      contributionCalendar {{
        totalContributions
        weeks {{ contributionDays {{ date contributionCount weekday }} }}
      }}
      commitContributionsByRepository(maxRepositories: 100) {{
        contributions {{ totalCount }}
        repository {{ {REPO_FIELDS} }}
      }}
      pullRequestContributionsByRepository(maxRepositories: 100) {{
        contributions {{ totalCount }}
        repository {{ nameWithOwner url owner {{ login }} stargazerCount }}
      }}
      issueContributionsByRepository(maxRepositories: 100) {{
        contributions {{ totalCount }}
        repository {{ nameWithOwner url owner {{ login }} }}
      }}
      pullRequestReviewContributionsByRepository(maxRepositories: 100) {{
        contributions {{ totalCount }}
        repository {{ nameWithOwner url owner {{ login }} }}
      }}
    }}
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
      totalCount
      nodes {{ {REPO_FIELDS} }}
    }}
  }}
}}
"""

SEARCH_QUERY = """
query($merged: String!, $mergedExternal: String!, $issuesClosed: String!, $prsOpened: String!) {
  merged: search(query: $merged, type: ISSUE, first: 1) { issueCount }
  mergedExternal: search(query: $mergedExternal, type: ISSUE, first: 30) {
    issueCount
    nodes { ... on PullRequest { title url mergedAt repository { nameWithOwner stargazerCount } } }
  }
  issuesClosed: search(query: $issuesClosed, type: ISSUE, first: 1) { issueCount }
  prsOpened: search(query: $prsOpened, type: ISSUE, first: 1) { issueCount }
}
"""


def fetch_graphql(login: str, year: int, start: dt.datetime, end: dt.datetime, token: str) -> dict:
    log("GraphQL: profile + contributions")
    data = graphql(MAIN_QUERY, {"login": login, "from": iso(start), "to": iso(end)}, token)
    user = data.get("user")
    if not user:
        raise RuntimeError(f"User '{login}' not found")

    rng = f"{start.date()}..{(end - dt.timedelta(seconds=1)).date()}"
    log("GraphQL: search counts (PRs / issues)")
    try:
        search = graphql(SEARCH_QUERY, {
            "merged": f"author:{login} is:pr is:merged merged:{rng}",
            "mergedExternal": f"author:{login} is:pr is:merged merged:{rng} -user:{login}",
            "issuesClosed": f"author:{login} is:issue is:closed closed:{rng}",
            "prsOpened": f"author:{login} is:pr created:{rng}",
        }, token)
    except RuntimeError as e:
        log(f"search skipped: {e}")
        search = {}

    cc = user.pop("contributionsCollection")
    repos_owned = user.pop("repositories")
    return {
        "profile": user,
        "contributions": cc,
        "owned_repositories": repos_owned,
        "search": search,
    }


# ---------------------------------------------------------------- REST fallback
def fetch_rest(login: str, year: int, start: dt.datetime, end: dt.datetime, token: str | None) -> dict:
    log("REST fallback (public data only)")
    profile, _ = request(f"{API}/users/{login}", token)
    repos, _ = request(f"{API}/users/{login}/repos?per_page=100&sort=pushed&type=owner", token)
    active = [r for r in repos if r.get("pushed_at") and r["pushed_at"] >= iso(start)]
    days: dict[str, int] = {}
    by_repo = []
    for r in active[:10]:
        q = urllib.parse.urlencode({"author": login, "since": iso(start), "until": iso(end), "per_page": 100})
        try:
            commits, _ = request(f"{API}/repos/{r['full_name']}/commits?{q}", token)
        except RuntimeError as e:
            log(f"skip {r['full_name']}: {e}")
            commits = []
        for c in commits:
            d = c["commit"]["author"]["date"][:10]
            days[d] = days.get(d, 0) + 1
        by_repo.append({
            "contributions": {"totalCount": len(commits)},
            "repository": rest_repo_to_graphql(r),
        })

    weeks = calendar_from_days(days, start, end)
    owned_nodes = [rest_repo_to_graphql(r) for r in repos]
    return {
        "profile": {
            "login": profile["login"], "name": profile.get("name"), "avatarUrl": profile.get("avatar_url"),
            "bio": profile.get("bio"), "url": profile.get("html_url"), "company": profile.get("company"),
            "location": profile.get("location"), "createdAt": profile.get("created_at"),
            "followers": {"totalCount": profile.get("followers", 0)},
            "following": {"totalCount": profile.get("following", 0)},
        },
        "contributions": {
            "totalCommitContributions": sum(days.values()),
            "totalIssueContributions": 0,
            "totalPullRequestContributions": 0,
            "totalPullRequestReviewContributions": 0,
            "totalRepositoryContributions": sum(1 for r in repos if (r.get("created_at") or "") >= iso(start)),
            "totalRepositoriesWithContributedCommits": sum(1 for x in by_repo if x["contributions"]["totalCount"]),
            "restrictedContributionsCount": 0,
            "contributionCalendar": {"totalContributions": sum(days.values()), "weeks": weeks},
            "commitContributionsByRepository": [x for x in by_repo if x["contributions"]["totalCount"]],
            "pullRequestContributionsByRepository": [],
            "issueContributionsByRepository": [],
            "pullRequestReviewContributionsByRepository": [],
        },
        "owned_repositories": {"totalCount": len(owned_nodes), "nodes": owned_nodes},
        "search": {},
    }


def rest_repo_to_graphql(r: dict) -> dict:
    lang = r.get("language")
    return {
        "nameWithOwner": r["full_name"], "name": r["name"], "description": r.get("description"),
        "url": r["html_url"], "homepageUrl": r.get("homepage"), "stargazerCount": r.get("stargazers_count", 0),
        "forkCount": r.get("forks_count", 0), "isPrivate": r.get("private", False), "isFork": r.get("fork", False),
        "isArchived": r.get("archived", False), "createdAt": r.get("created_at"), "pushedAt": r.get("pushed_at"),
        "owner": {"login": r["owner"]["login"]},
        "primaryLanguage": {"name": lang, "color": None} if lang else None,
        "repositoryTopics": {"nodes": [{"topic": {"name": t}} for t in r.get("topics", [])]},
        "languages": {"totalSize": 1, "edges": [{"size": 1, "node": {"name": lang, "color": None}}] if lang else []},
        "releases": {"totalCount": 0, "nodes": []},
    }


def calendar_from_days(days: dict[str, int], start: dt.datetime, end: dt.datetime) -> list:
    weeks, week = [], []
    d = start.date()
    while d < end.date():
        week.append({"date": d.isoformat(), "contributionCount": days.get(d.isoformat(), 0),
                     "weekday": (d.weekday() + 1) % 7})
        if (d.weekday() + 1) % 7 == 6:
            weeks.append({"contributionDays": week})
            week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})
    return weeks


# ---------------------------------------------------------------- commit samples
def fetch_commit_samples(login: str, repos: list[dict], start: dt.datetime, end: dt.datetime,
                         token: str | None, max_repos: int, pages: int) -> list[dict]:
    """Commit timestamps + messages for the top repos (used for hour-of-day and narrative)."""
    samples = []
    for item in repos[:max_repos]:
        name = item["repository"]["nameWithOwner"]
        commits = []
        for page in range(1, pages + 1):
            q = urllib.parse.urlencode({"author": login, "since": iso(start), "until": iso(end),
                                        "per_page": 100, "page": page})
            try:
                batch, _ = request(f"{API}/repos/{name}/commits?{q}", token)
            except RuntimeError as e:
                log(f"commit sample skipped for {name}: {str(e)[:120]}")
                break
            if not batch:
                break
            for c in batch:
                commits.append({
                    "date": c["commit"]["author"]["date"],
                    "message": c["commit"]["message"].split("\n", 1)[0][:160],
                })
            if len(batch) < 100:
                break
        log(f"commit sample {name}: {len(commits)}")
        samples.append({"repository": name, "commits": commits})
    return samples


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True, help="GitHub login")
    ap.add_argument("--year", type=int, default=dt.date.today().year)
    ap.add_argument("--tz", default="UTC", help="IANA timezone for hour-of-day stats, e.g. Asia/Taipei")
    ap.add_argument("--token", help="GitHub token (otherwise GITHUB_TOKEN/GH_TOKEN/gh auth token)")
    ap.add_argument("--sample-repos", type=int, default=8, help="repos to sample commit times from")
    ap.add_argument("--sample-pages", type=int, default=3, help="pages of 100 commits per sampled repo")
    ap.add_argument("-o", "--output", default="raw.json")
    args = ap.parse_args()

    start = dt.datetime(args.year, 1, 1, tzinfo=dt.timezone.utc)
    end = dt.datetime(args.year + 1, 1, 1, tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    if end > now:
        end = now.replace(microsecond=0)

    token = get_token(args.token)
    if token:
        try:
            raw = fetch_graphql(args.user, args.year, start, end, token)
            source = "graphql"
        except RuntimeError as e:
            log(f"GraphQL failed ({e}); falling back to REST")
            raw, source = fetch_rest(args.user, args.year, start, end, token), "rest"
    else:
        log("No token found - using public REST fallback (limited). Set GITHUB_TOKEN for full data.")
        raw, source = fetch_rest(args.user, args.year, start, end, None), "rest-public"

    by_repo = sorted(raw["contributions"]["commitContributionsByRepository"],
                     key=lambda x: -x["contributions"]["totalCount"])
    raw["commit_samples"] = fetch_commit_samples(args.user, by_repo, start, end, token,
                                                 args.sample_repos, args.sample_pages)
    raw["meta"] = {
        "user": args.user, "year": args.year, "tz": args.tz, "source": source,
        "range": {"from": iso(start), "to": iso(end)},
        "generated_at": iso(now),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=1)
    log(f"saved {args.output} (source={source})")


if __name__ == "__main__":
    main()
