"""Authenticated private activity, including calendars that omit private events.

Only aggregate coverage metadata is exposed publicly. All connections are paginated;
request failures abort inclusive collection instead of silently returning public data.
"""
from __future__ import annotations

import collections
import datetime as dt
from zoneinfo import ZoneInfo

PROFILE_QUERY = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  viewer { id login }
  user(login:$login){
    login name avatarUrl bio url company location createdAt
    followers{totalCount} following{totalCount}
    contributionsCollection(from:$from,to:$to){
      totalCommitContributions totalIssueContributions totalPullRequestContributions
      totalPullRequestReviewContributions totalRepositoryContributions
      totalRepositoriesWithContributedCommits restrictedContributionsCount
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}
      commitContributionsByRepository(maxRepositories:100){contributions{totalCount} repository{nameWithOwner isPrivate}}
      pullRequestContributionsByRepository(maxRepositories:100){contributions{totalCount} repository{nameWithOwner isPrivate}}
      issueContributionsByRepository(maxRepositories:100){contributions{totalCount} repository{nameWithOwner isPrivate}}
      pullRequestReviewContributionsByRepository(maxRepositories:100){contributions{totalCount} repository{nameWithOwner isPrivate}}
      repositoryContributions(first:100){nodes{repository{isPrivate}}}
    }
  }
}
"""


def iso(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def connection_pages(query, document, variables, select):
    """Yield complete connection pages, rejecting a cursor that does not advance."""
    cursor = None
    while True:
        page = select(query(document, {**variables, "after": cursor}))
        yield page
        info = page["pageInfo"]
        if not info["hasNextPage"]:
            return
        following = info["endCursor"]
        if not following or following == cursor:
            raise RuntimeError("GitHub returned a non-advancing pagination cursor")
        cursor = following


def commit_history(query, repo, author_id, start, end):
    """Read an author's complete default-branch history, pinning the initial head."""
    head = None
    cursor = None
    commits = {}
    while True:
        target = "object(oid:$head){" if head else "defaultBranchRef{target{"
        close = "}" if head else "}}"
        document = ("query($id:ID!,$after:String,$from:GitTimestamp!,$to:GitTimestamp!,$author:ID!"
                    + (",$head:GitObjectID!" if head else "") + "){node(id:$id){... on Repository{"
                    + target + "... on Commit{oid history(first:100,after:$after,since:$from,until:$to,author:{id:$author}){"
                    "pageInfo{hasNextPage endCursor} nodes{oid authoredDate messageHeadline}}}" + close + "}}}")
        variables = {"id": repo["id"], "author": author_id, "from": iso(start), "to": iso(end), "after": cursor}
        if head:
            variables["head"] = head
        node = query(document, variables)["node"]
        if node is None:
            raise RuntimeError("Access to a private repository changed during collection")
        obj = node.get("object") if head else (node.get("defaultBranchRef") or {}).get("target")
        if obj is None:
            if head:
                raise RuntimeError("The pinned private repository history is no longer accessible")
            return []  # empty repository
        head = obj["oid"]
        page = obj["history"]
        for commit in page["nodes"]:
            date = dt.datetime.fromisoformat(commit["authoredDate"].replace("Z", "+00:00"))
            if start <= date < end:
                commits[commit["oid"]] = commit
        info = page["pageInfo"]
        if not info["hasNextPage"]:
            return list(commits.values())
        following = info["endCursor"]
        if not following or following == cursor:
            raise RuntimeError("GitHub returned a non-advancing history cursor")
        cursor = following


def authored_items(query, field, start, end):
    document = ("query($after:String){viewer{" + field
                + "(first:100,after:$after,orderBy:{field:CREATED_AT,direction:DESC}){"
                "pageInfo{hasNextPage endCursor} nodes{createdAt repository{nameWithOwner isPrivate}}}}}")
    items = []
    for page in connection_pages(query, document, {}, lambda d: d["viewer"][field]):
        for item in page["nodes"]:
            when = dt.datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
            if start <= when < end:
                items.append(item)
        if page["nodes"] and page["nodes"][-1]["createdAt"] < iso(start):
            break
    return items


def private_reviews(query, login, start, end):
    # No upper updated bound: a PR reviewed in the requested year can be updated later.
    search = f"reviewed-by:{login} is:pr is:private updated:>={start.date()}"
    document = """query($q:String!,$after:String){search(query:$q,type:ISSUE,first:100,after:$after){
      issueCount pageInfo{hasNextPage endCursor} nodes{... on PullRequest{id repository{nameWithOwner isPrivate}}}}}"""
    by_repo = collections.Counter()
    dates = []
    seen = set()
    for page in connection_pages(query, document, {"q": search}, lambda d: d["search"]):
        if page["issueCount"] > 1000:
            raise RuntimeError("Private reviewed-PR search exceeds GitHub's 1,000-result cap; narrow the review scope")
        for pr in page["nodes"]:
            if not pr or pr["id"] in seen or not pr["repository"]["isPrivate"]:
                continue
            seen.add(pr["id"])
            reviews_query = """query($id:ID!,$login:String!,$after:String){node(id:$id){... on PullRequest{
              reviews(first:100,after:$after,author:$login){pageInfo{hasNextPage endCursor}
                nodes{author{login} submittedAt}}}}}"""
            for reviews in connection_pages(query, reviews_query, {"id": pr["id"], "login": login},
                                            lambda d: d["node"]["reviews"]):
                for review in reviews["nodes"]:
                    submitted = review.get("submittedAt")
                    if not submitted or (review.get("author") or {}).get("login", "").lower() != login.lower():
                        continue
                    date = dt.datetime.fromisoformat(submitted.replace("Z", "+00:00"))
                    if start <= date < end:
                        by_repo[pr["repository"]["nameWithOwner"]] += 1
                        dates.append(date)
    return by_repo, dates


def collect(login, start, end, tz_name, query, repo_fields, search_query, log):
    """Return the common raw structure, enriched with all accessible owned private repos."""
    timezone = ZoneInfo(tz_name)  # reject invalid timezone before private collection
    data = query(PROFILE_QUERY, {"login": login, "from": iso(start), "to": iso(end)})
    viewer = data["viewer"]
    if viewer["login"].lower() != login.lower():
        raise RuntimeError("--include-private requires --user to match the authenticated GitHub account")
    user = data["user"]
    if not user:
        raise RuntimeError("GitHub account not found")
    cc = user.pop("contributionsCollection")
    by_repo_keys = ("commitContributionsByRepository", "pullRequestContributionsByRepository",
                    "issueContributionsByRepository", "pullRequestReviewContributionsByRepository")
    creations = cc.pop("repositoryContributions")["nodes"]
    calendar_has_private = bool(cc.get("restrictedContributionsCount")) or any(
        row["repository"].get("isPrivate") for key in by_repo_keys for row in cc.get(key, [])) or any(
        (row.get("repository") or {}).get("isPrivate") for row in creations)

    document = ("query($after:String){viewer{repositories(first:20,after:$after,ownerAffiliations:OWNER,"
                "orderBy:{field:CREATED_AT,direction:DESC}){pageInfo{hasNextPage endCursor} nodes{id " + repo_fields + "}}}}")
    owned = [r for page in connection_pages(query, document, {}, lambda d: d["viewer"]["repositories"])
             for r in page["nodes"]]
    repositories = {r["nameWithOwner"]: r for r in owned}
    # Contributions to public repositories owned by others still need their metadata.
    for row in cc["commitContributionsByRepository"]:
        name = row["repository"]["nameWithOwner"]
        if name not in repositories:
            owner, name_only = name.split("/", 1)
            document = "query($owner:String!,$name:String!){repository(owner:$owner,name:$name){" + repo_fields + "}}"
            repositories[name] = query(document, {"owner": owner, "name": name_only})["repository"]
        row["repository"] = repositories[name]

    private = [r for r in owned if r["isPrivate"] and not r["isFork"]]
    log(f"private collection: {len(private)} accessible owned non-fork repositories")
    history = {}
    for index, repo in enumerate(private, 1):
        history[repo["nameWithOwner"]] = commit_history(query, repo, viewer["id"], start, end)
        if index % 10 == 0 or index == len(private):
            log(f"private histories: {index}/{len(private)}")
    all_prs = authored_items(query, "pullRequests", start, end)
    all_issues = authored_items(query, "issues", start, end)
    prs = [p for p in all_prs if p["repository"]["isPrivate"]]
    issues = [i for i in all_issues if i["repository"]["isPrivate"]]
    reviews, review_dates = private_reviews(query, login, start, end)
    created = [r for r in private if iso(start) <= r["createdAt"] < iso(end)]
    days = collections.Counter()

    def add_date(value):
        if isinstance(value, str):
            value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        days[value.astimezone(timezone).date().isoformat()] += 1

    for commits in history.values():
        for commit in commits:
            add_date(commit["authoredDate"])
    for item in prs + issues:
        add_date(item["createdAt"])
    for repo in created:
        add_date(repo["createdAt"])
    for date in review_dates:
        add_date(date)

    # Replace matching private records rather than appending duplicates. Never replace
    # the already-counted GitHub calendar with a second copy of private activity.
    private_names = set(history)
    existing = [r for r in cc[by_repo_keys[0]] if r["repository"]["nameWithOwner"] not in private_names]
    cc[by_repo_keys[0]] = existing + [
        {"repository": repositories[name], "contributions": {"totalCount": len(commits)}}
        for name, commits in history.items() if commits]
    for field, items in [(by_repo_keys[1], prs), (by_repo_keys[2], issues)]:
        counts = collections.Counter(x["repository"]["nameWithOwner"] for x in items)
        cc[field] = [r for r in cc[field] if not r["repository"].get("isPrivate")] + [
            {"repository": {"nameWithOwner": name, "isPrivate": True}, "contributions": {"totalCount": n}}
            for name, n in counts.items()]
    cc[by_repo_keys[3]] = [r for r in cc[by_repo_keys[3]] if not r["repository"].get("isPrivate")] + [
        {"repository": {"nameWithOwner": name, "isPrivate": True}, "contributions": {"totalCount": n}}
        for name, n in reviews.items()]
    private_commits = sum(map(len, history.values()))
    private_count = sum(days.values())
    if not calendar_has_private:
        cc["totalCommitContributions"] += private_commits
        cc["totalPullRequestContributions"] += len(prs)
        cc["totalIssueContributions"] += len(issues)
        cc["totalPullRequestReviewContributions"] += sum(reviews.values())
        cc["totalRepositoryContributions"] += len(created)
        cc["restrictedContributionsCount"] = private_count
        calendar = cc["contributionCalendar"]
        present = set()
        for week in calendar["weeks"]:
            for day in week["contributionDays"]:
                date = day["date"]
                day["contributionCount"] += days.get(date, 0)
                present.add(date)
        # Events near the UTC end boundary may fall on the next local date.
        missing = sorted(set(days) - present)
        for date in missing:
            local = dt.date.fromisoformat(date)
            if local.year == start.year:
                calendar["weeks"].append({"contributionDays": [{"date": date,
                    "contributionCount": days[date], "weekday": (local.weekday() + 1) % 7}]})
        calendar["totalContributions"] = sum(d["contributionCount"] for w in calendar["weeks"] for d in w["contributionDays"])
    else:
        # Anonymous private calendar squares need not be broken down by activity type.
        # Enrich the typed counts from complete connections without adding calendar
        # events again. Preserve larger official counts when visibility is limited.
        cc["totalCommitContributions"] = max(cc["totalCommitContributions"],
            sum(r["contributions"]["totalCount"] for r in cc[by_repo_keys[0]]))
        cc["totalPullRequestContributions"] = max(cc["totalPullRequestContributions"], len(all_prs))
        cc["totalIssueContributions"] = max(cc["totalIssueContributions"], len(all_issues))
        cc["totalPullRequestReviewContributions"] = max(cc["totalPullRequestReviewContributions"],
            sum(r["contributions"]["totalCount"] for r in cc[by_repo_keys[3]]))
    cc["totalRepositoriesWithContributedCommits"] = max(
        cc["totalRepositoriesWithContributedCommits"], len(cc[by_repo_keys[0]]))
    rng = f"{start.date()}..{(end - dt.timedelta(seconds=1)).date()}"
    search = query(search_query, {"merged": f"author:{login} is:pr is:merged merged:{rng}",
        "mergedExternal": f"author:{login} is:pr is:merged merged:{rng} -user:{login}",
        "issuesClosed": f"author:{login} is:issue is:closed closed:{rng}",
        "prsOpened": f"author:{login} is:pr created:{rng}"})
    return {"profile": user, "contributions": cc,
            "owned_repositories": {"totalCount": len(owned), "nodes": owned}, "search": search,
            "private_activity": {"repositories_visible": len(private),
                "repositories_with_commits": sum(bool(v) for v in history.values()), "commits": private_commits,
                "pull_requests": len(prs), "issues": len(issues), "reviews": sum(reviews.values()),
                "repositories_created": len(created), "contributions": private_count,
                "calendar_reconstructed": not calendar_has_private and private_count > 0}}
