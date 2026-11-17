"""Search-API data source for fetch_github_year.py.

Builds the same raw structure as the GraphQL path using only GitHub's public search
endpoints (search/commits, search/issues, search/repositories, search/users). Works
without a token (10 req/min) or with one (30 req/min), and in environments where
GraphQL / user endpoints are not reachable.

Differences from GraphQL: public activity only, the calendar is rebuilt from commit +
PR + issue dates, repos only carry their primary language, review count is approximate,
and releases are unknown.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

API = "https://api.github.com"
UA = "github-year-review-skill"
MAX_RESULTS = 1000  # search API hard cap per query

LANG_COLORS = {
    "TypeScript": "#3178c6", "JavaScript": "#f1e05a", "Python": "#3572A5", "HTML": "#e34c26",
    "CSS": "#563d7c", "Go": "#00ADD8", "Rust": "#dea584", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Swift": "#F05138", "C": "#555555", "C++": "#f34b7d", "C#": "#178600", "Ruby": "#701516",
    "PHP": "#4F5D95", "Shell": "#89e051", "Dart": "#00B4AB", "Vue": "#41b883", "Svelte": "#ff3e00",
    "Lua": "#000080", "Jupyter Notebook": "#DA5B0B", "SCSS": "#c6538c", "Astro": "#ff5a03",
    "MDX": "#fcb32c", "Dockerfile": "#384d54", "GDScript": "#355570", "Zig": "#ec915c",
    "Elixir": "#6e4a7e", "Scala": "#c22d40", "Haskell": "#5e5086", "Objective-C": "#438eff",
    "PowerShell": "#012456", "R": "#198CE7", "Solidity": "#AA6746", "TeX": "#3D6117",
}


def log(msg: str) -> None:
    print(f"[search] {msg}", file=sys.stderr)


class Search:
    def __init__(self, token: str | None):
        self.token = token

    def get(self, path: str, params: dict) -> dict:
        url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
        for attempt in range(8):
            headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                    remaining = int(r.headers.get("X-RateLimit-Remaining", "1"))
                    reset = int(r.headers.get("X-RateLimit-Reset", "0"))
                    data = json.loads(r.read().decode())
                if remaining == 0 and reset:
                    wait = max(1, reset - int(time.time()) + 1)
                    log(f"rate limit reached, sleeping {wait}s")
                    time.sleep(wait)
                return data
            except urllib.error.HTTPError as e:
                if e.code == 401 and self.token:
                    log("token rejected, continuing unauthenticated")
                    self.token = None
                    continue
                if e.code in (403, 429):
                    reset = int(e.headers.get("X-RateLimit-Reset", "0") or 0)
                    retry = int(e.headers.get("Retry-After", "0") or 0)
                    wait = retry or (max(1, reset - int(time.time()) + 1) if reset else 15 * (attempt + 1))
                    log(f"HTTP {e.code}, retrying in {min(wait, 90)}s")
                    time.sleep(min(wait, 90))
                    continue
                if e.code == 422:
                    return {"total_count": 0, "items": []}
                raise RuntimeError(f"HTTP {e.code} for {url}: {e.read().decode(errors='replace')[:300]}") from None
        raise RuntimeError(f"giving up on {url}")

    def collect(self, path: str, query_fn, start: dt.date, end: dt.date, extra=None) -> list[dict]:
        """Fetch every item for query_fn(range) between start..end (inclusive dates),
        splitting the date range whenever a slice exceeds the 1000-result cap."""
        rng = f"{start.isoformat()}..{end.isoformat()}"
        first = self.get(path, {"q": query_fn(rng), "per_page": 100, "page": 1, **(extra or {})})
        total = first.get("total_count", 0)
        if total == 0:
            return []
        if total > MAX_RESULTS and start < end:
            mid = start + (end - start) / 2
            return (self.collect(path, query_fn, start, mid, extra)
                    + self.collect(path, query_fn, mid + dt.timedelta(days=1), end, extra))
        items = list(first.get("items", []))
        pages = min(MAX_RESULTS, total) // 100 + (1 if min(MAX_RESULTS, total) % 100 else 0)
        for page in range(2, pages + 1):
            items += self.get(path, {"q": query_fn(rng), "per_page": 100, "page": page, **(extra or {})}).get("items", [])
        log(f"{path} {rng}: {len(items)}/{total}")
        return items


def repo_node(r: dict) -> dict:
    lang = r.get("language")
    return {
        "nameWithOwner": r["full_name"], "name": r["name"], "description": r.get("description"),
        "url": r.get("html_url"), "homepageUrl": r.get("homepage"),
        "stargazerCount": r.get("stargazers_count", 0), "forkCount": r.get("forks_count", 0),
        "isPrivate": r.get("private", False), "isFork": r.get("fork", False), "isArchived": r.get("archived", False),
        "createdAt": r.get("created_at"), "pushedAt": r.get("pushed_at"),
        "owner": {"login": r["owner"]["login"]},
        "primaryLanguage": {"name": lang, "color": LANG_COLORS.get(lang)} if lang else None,
        "repositoryTopics": {"nodes": [{"topic": {"name": t}} for t in r.get("topics", []) or []]},
        "languages": {"totalSize": 1, "edges": [{"size": 1, "node": {"name": lang, "color": LANG_COLORS.get(lang)}}] if lang else []},
        "releases": {"totalCount": 0, "nodes": []},
    }


def fetch_search(login: str, year: int, start: dt.datetime, end: dt.datetime, token: str | None, tz_name: str) -> dict:
    s = Search(token)
    tz = dt.timezone.utc
    if ZoneInfo:
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            pass
    d0, d1 = start.date(), (end - dt.timedelta(seconds=1)).date()

    log("profile")
    users = s.get("search/users", {"q": f"user:{login}", "per_page": 1}).get("items", [])
    u = users[0] if users else {"login": login, "avatar_url": None, "html_url": f"https://github.com/{login}"}

    log("repositories")
    repos: list[dict] = []
    page = 1
    while True:
        batch = s.get("search/repositories", {"q": f"user:{login} fork:true", "per_page": 100, "page": page,
                                              "sort": "updated"})
        repos += batch.get("items", [])
        if len(batch.get("items", [])) < 100 or len(repos) >= min(MAX_RESULTS, batch.get("total_count", 0)):
            break
        page += 1
    repo_by_name = {r["full_name"]: r for r in repos}

    log("commits")
    commits = s.collect("search/commits", lambda rng: f"author:{login} author-date:{rng}", d0, d1,
                        {"sort": "author-date", "order": "asc"})
    seen, uniq = set(), []
    for c in commits:
        if c["sha"] in seen:
            continue
        seen.add(c["sha"])
        uniq.append(c)

    log("pull requests / issues")
    prs = s.collect("search/issues", lambda rng: f"author:{login} is:pr created:{rng}", d0, d1)
    issues = s.collect("search/issues", lambda rng: f"author:{login} is:issue created:{rng}", d0, d1)
    rng = f"{d0}..{d1}"
    merged = s.get("search/issues", {"q": f"author:{login} is:pr is:merged merged:{rng}", "per_page": 1})
    ext = s.get("search/issues", {"q": f"author:{login} is:pr is:merged merged:{rng} -user:{login}", "per_page": 30})
    closed = s.get("search/issues", {"q": f"author:{login} is:issue is:closed closed:{rng}", "per_page": 1})
    reviewed = s.get("search/issues", {"q": f"reviewed-by:{login} -author:{login} is:pr updated:{rng}", "per_page": 1})

    # calendar (local dates in the user's timezone)
    days: collections.Counter = collections.Counter()
    by_repo: collections.Counter = collections.Counter()
    samples: dict[str, list] = collections.defaultdict(list)
    for c in uniq:
        t = dt.datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00"))
        days[t.astimezone(tz).date().isoformat()] += 1
        name = c["repository"]["full_name"]
        by_repo[name] += 1
        if name not in repo_by_name:
            repo_by_name[name] = c["repository"]
        samples[name].append({"date": t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "message": c["commit"]["message"].split("\n", 1)[0][:160]})
    for it in prs + issues:
        t = dt.datetime.fromisoformat(it["created_at"].replace("Z", "+00:00"))
        days[t.astimezone(tz).date().isoformat()] += 1

    weeks, week = [], []
    d = d0
    while d <= d1:
        wd = (d.weekday() + 1) % 7
        week.append({"date": d.isoformat(), "contributionCount": days.get(d.isoformat(), 0), "weekday": wd})
        if wd == 6:
            weeks.append({"contributionDays": week})
            week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})

    def repo_of(item):  # issues/PRs carry repository_url only
        return item["repository_url"].split("/repos/", 1)[1]

    pr_by_repo = collections.Counter(repo_of(p) for p in prs)
    is_by_repo = collections.Counter(repo_of(i) for i in issues)
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    def node(name):
        r = repo_by_name.get(name)
        if r and "full_name" in r and "stargazers_count" in r:
            return repo_node(r)
        if r:  # minimal repository object from commit search
            return repo_node({**r, "stargazers_count": 0, "forks_count": 0})
        owner, nm = name.split("/", 1)
        return repo_node({"full_name": name, "name": nm, "owner": {"login": owner},
                          "html_url": f"https://github.com/{name}"})

    log(f"{len(uniq)} commits, {len(prs)} PRs, {len(issues)} issues, {len(repos)} repos")
    return {
        "profile": {
            "login": u["login"], "name": None, "avatarUrl": u.get("avatar_url"), "bio": None,
            "url": u.get("html_url"), "company": None, "location": None, "createdAt": None,
            "followers": {"totalCount": 0}, "following": {"totalCount": 0},
        },
        "contributions": {
            "totalCommitContributions": len(uniq),
            "totalIssueContributions": len(issues),
            "totalPullRequestContributions": len(prs),
            "totalPullRequestReviewContributions": reviewed.get("total_count", 0),
            "totalRepositoryContributions": sum(1 for r in repos if (r.get("created_at") or "") >= start_iso),
            "totalRepositoriesWithContributedCommits": len(by_repo),
            "restrictedContributionsCount": 0,
            "contributionCalendar": {"totalContributions": sum(days.values()), "weeks": weeks},
            "commitContributionsByRepository": [
                {"contributions": {"totalCount": n}, "repository": node(name)} for name, n in by_repo.most_common()],
            "pullRequestContributionsByRepository": [
                {"contributions": {"totalCount": n}, "repository": {"nameWithOwner": k}} for k, n in pr_by_repo.items()],
            "issueContributionsByRepository": [
                {"contributions": {"totalCount": n}, "repository": {"nameWithOwner": k}} for k, n in is_by_repo.items()],
            "pullRequestReviewContributionsByRepository": [],
        },
        "owned_repositories": {"totalCount": len(repos), "nodes": [repo_node(r) for r in repos]},
        "search": {
            "merged": {"issueCount": merged.get("total_count", 0)},
            "mergedExternal": {"issueCount": ext.get("total_count", 0), "nodes": [
                {"title": i["title"], "url": i["html_url"], "mergedAt": (i.get("pull_request") or {}).get("merged_at"),
                 "repository": {"nameWithOwner": repo_of(i)}} for i in ext.get("items", [])]},
            "issuesClosed": {"issueCount": closed.get("total_count", 0)},
            "prsOpened": {"issueCount": len(prs)},
        },
        "commit_samples": [{"repository": k, "commits": v}
                           for k, v in sorted(samples.items(), key=lambda kv: -len(kv[1]))],
    }
