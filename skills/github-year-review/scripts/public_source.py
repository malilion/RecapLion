"""Public-only GraphQL collection (``--scope public`` with a token).

A token belonging to the account owner makes GitHub count private contributions in the
calendar and in every total. This module rebuilds the year from individual contribution
records and keeps only those in public repositories, so a public report never includes
private activity — not even as anonymous counts.

Commit contributions are read per month (each repository then has at most 31 day records,
well under the 100-record page); a month with 100 repositories is split further.
Pull requests, issues, reviews and repository creations are read from their paginated
connections over the whole range.
"""
from __future__ import annotations

import collections
import datetime as dt

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from private_source import connection_pages, iso

PROFILE_QUERY = """
query($login:String!){
  user(login:$login){
    login name avatarUrl bio url company location createdAt
    followers{totalCount} following{totalCount}
  }
}
"""

COMMITS_QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){contributionsCollection(from:$from,to:$to){
    commitContributionsByRepository(maxRepositories:100){
      repository{nameWithOwner isPrivate}
      contributions(first:100){totalCount nodes{occurredAt commitCount}}
    }
  }}
}
"""

# connection field -> (node selection, path from node to the repository)
EVENTS = {
    "pullRequestContributions": ("occurredAt pullRequest{repository{nameWithOwner isPrivate}}", ("pullRequest", "repository")),
    "issueContributions": ("occurredAt issue{repository{nameWithOwner isPrivate}}", ("issue", "repository")),
    "pullRequestReviewContributions": ("occurredAt repository{nameWithOwner isPrivate}", ("repository",)),
    "repositoryContributions": ("occurredAt repository{nameWithOwner isPrivate isFork}", ("repository",)),
}


def month_windows(start: dt.datetime, end: dt.datetime):
    cur = start
    while cur < end:
        nxt = dt.datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1, tzinfo=dt.timezone.utc)
        yield cur, min(nxt, end)
        cur = nxt


def commit_rows(query, login, start, end, log):
    """Public commit contributions: {repo: [(date, count), ...]} for start..end."""
    rows: dict[str, list] = collections.defaultdict(list)

    def window(a, b):
        data = query(COMMITS_QUERY, {"login": login, "from": iso(a), "to": iso(b - dt.timedelta(seconds=1))})
        repos = data["user"]["contributionsCollection"]["commitContributionsByRepository"]
        if len(repos) >= 100 and b - a > dt.timedelta(days=1):
            mid = a + (b - a) / 2
            mid = dt.datetime(mid.year, mid.month, mid.day, tzinfo=dt.timezone.utc)
            if a < mid < b:
                window(a, mid)
                window(mid, b)
                return
        if len(repos) >= 100:
            raise RuntimeError("More than 100 repositories with commits in a single day; cannot list them all")
        for r in repos:
            if r["repository"]["isPrivate"]:
                continue
            conn = r["contributions"]
            if conn["totalCount"] > len(conn["nodes"]):
                raise RuntimeError(f"Incomplete commit contribution list for {r['repository']['nameWithOwner']}")
            for n in conn["nodes"]:
                rows[r["repository"]["nameWithOwner"]].append((n["occurredAt"][:10], n["commitCount"]))

    for a, b in month_windows(start, end):
        window(a, b)
    log(f"public commit contributions: {sum(c for v in rows.values() for _, c in v)} in {len(rows)} repositories")
    return rows


def event_rows(query, login, start, end, field):
    selection, path = EVENTS[field]
    document = ("query($login:String!,$from:DateTime!,$to:DateTime!,$after:String){user(login:$login){"
                "contributionsCollection(from:$from,to:$to){" + field +
                "(first:100,after:$after){pageInfo{hasNextPage endCursor} nodes{" + selection + "}}}}}")
    variables = {"login": login, "from": iso(start), "to": iso(end - dt.timedelta(seconds=1))}
    out = []
    for page in connection_pages(query, document, variables,
                                 lambda d: d["user"]["contributionsCollection"][field]):
        for node in page["nodes"]:
            repo = node
            for key in path:
                repo = (repo or {}).get(key)
            if repo and not repo.get("isPrivate"):
                out.append((node["occurredAt"], repo))
    return out


def weeks_from_days(days: collections.Counter, start: dt.date, end: dt.date) -> list:
    weeks, week = [], []
    d = start
    while d <= end:
        wd = (d.weekday() + 1) % 7
        week.append({"date": d.isoformat(), "contributionCount": days.get(d.isoformat(), 0), "weekday": wd})
        if wd == 6:
            weeks.append({"contributionDays": week})
            week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append({"contributionDays": week})
    return weeks


def collect(login, start, end, tz_name, query, repo_fields, search_query, log):
    """Return the common raw structure built from public repositories only."""
    timezone = ZoneInfo(tz_name) if ZoneInfo else dt.timezone.utc
    user = query(PROFILE_QUERY, {"login": login})["user"]
    if not user:
        raise RuntimeError("GitHub account not found")

    commits = commit_rows(query, login, start, end, log)
    events = {field: event_rows(query, login, start, end, field) for field in EVENTS}

    days: collections.Counter = collections.Counter()
    for items in commits.values():
        for date, count in items:
            days[date] += count
    for field, items in events.items():
        for occurred, _ in items:
            t = dt.datetime.fromisoformat(occurred.replace("Z", "+00:00"))
            days[t.astimezone(timezone).date().isoformat()] += 1

    document = ("query($login:String!,$after:String){user(login:$login){repositories(first:50,after:$after,"
                "privacy:PUBLIC,ownerAffiliations:OWNER,orderBy:{field:CREATED_AT,direction:DESC}){"
                "pageInfo{hasNextPage endCursor} nodes{" + repo_fields + "}}}}")
    owned = [r for page in connection_pages(query, document, {"login": login}, lambda d: d["user"]["repositories"])
             for r in page["nodes"] if not r.get("isPrivate")]
    repositories = {r["nameWithOwner"]: r for r in owned}
    for name in commits:
        if name not in repositories:
            owner, short = name.split("/", 1)
            doc = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){" + repo_fields + "}}"
            repo = query(doc, {"owner": owner, "name": short})["repository"]
            if repo and not repo.get("isPrivate"):
                repositories[name] = repo

    def by_repo(items):
        counts = collections.Counter(repo["nameWithOwner"] for _, repo in items)
        return [{"repository": {"nameWithOwner": n, "isPrivate": False}, "contributions": {"totalCount": c}}
                for n, c in counts.most_common()]

    commit_totals = {name: sum(c for _, c in items) for name, items in commits.items() if name in repositories}
    created = [repo for _, repo in events["repositoryContributions"]]
    cc = {
        "totalCommitContributions": sum(commit_totals.values()),
        "totalIssueContributions": len(events["issueContributions"]),
        "totalPullRequestContributions": len(events["pullRequestContributions"]),
        "totalPullRequestReviewContributions": len(events["pullRequestReviewContributions"]),
        "totalRepositoryContributions": len(created),
        "totalRepositoriesWithContributedCommits": len(commit_totals),
        "restrictedContributionsCount": 0,
        "contributionCalendar": {
            "totalContributions": sum(days.values()),
            "weeks": weeks_from_days(days, start.date(), (end - dt.timedelta(seconds=1)).date()),
        },
        "commitContributionsByRepository": [
            {"repository": repositories[n], "contributions": {"totalCount": c}}
            for n, c in sorted(commit_totals.items(), key=lambda kv: -kv[1])],
        "pullRequestContributionsByRepository": by_repo(events["pullRequestContributions"]),
        "issueContributionsByRepository": by_repo(events["issueContributions"]),
        "pullRequestReviewContributionsByRepository": by_repo(events["pullRequestReviewContributions"]),
    }

    rng = f"{start.date()}..{(end - dt.timedelta(seconds=1)).date()}"
    search = query(search_query, {
        "merged": f"author:{login} is:pr is:public is:merged merged:{rng}",
        "mergedExternal": f"author:{login} is:pr is:public is:merged merged:{rng} -user:{login}",
        "issuesClosed": f"author:{login} is:issue is:public is:closed closed:{rng}",
        "prsOpened": f"author:{login} is:pr is:public created:{rng}",
    })
    return {"profile": user, "contributions": cc,
            "owned_repositories": {"totalCount": len(owned), "nodes": owned}, "search": search}
