#!/usr/bin/env python3
"""Turn raw.json (from fetch_github_year.py) into analysis.json:
yearly stats, project list, language mix and unlocked achievements.

Usage:
  python3 analyze.py raw.json -o analysis.json [--exclude-private]
"""
from __future__ import annotations

import argparse
import calendar
import collections
import datetime as dt
import json
import sys

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

TIERS = ["common", "rare", "epic", "legendary"]

# ------------------------------------------------------------------ achievements
# Each achievement has 4 thresholds -> common / rare / epic / legendary.
# `metric` is a key in the stats dict built below. `min_sample` guards ratio metrics.
ACHIEVEMENTS = [
    dict(id="eternal_flame", icon="🔥", metric="longest_streak", unit="days",
         thresholds=[7, 30, 100, 200],
         title={"zh": "不滅之火", "en": "Eternal Flame"},
         desc={"zh": "連續 {v} 天都有貢獻", "en": "Contributed {v} days in a row"}),
    dict(id="forged", icon="⚒️", metric="total_contributions", unit="",
         thresholds=[100, 500, 1000, 3000],
         title={"zh": "千錘百鍊", "en": "Forged in Commits"},
         desc={"zh": "今年累積 {v} 次貢獻", "en": "{v} contributions this year"}),
    dict(id="daily_builder", icon="📅", metric="active_days", unit="days",
         thresholds=[50, 100, 200, 300],
         title={"zh": "日更職人", "en": "Daily Builder"},
         desc={"zh": "一年中有 {v} 天在寫程式", "en": "Active on {v} days"}),
    dict(id="genesis", icon="🌱", metric="repos_created", unit="",
         thresholds=[1, 5, 10, 20],
         title={"zh": "創世者", "en": "Genesis"},
         desc={"zh": "今年從零開了 {v} 個新專案", "en": "Started {v} new repositories"}),
    dict(id="polyglot", icon="🗣️", metric="language_count", unit="",
         thresholds=[2, 4, 6, 8],
         title={"zh": "多語通", "en": "Polyglot"},
         desc={"zh": "使用了 {v} 種程式語言", "en": "Wrote code in {v} languages"}),
    dict(id="merge_master", icon="🔀", metric="prs_merged", unit="",
         thresholds=[5, 25, 100, 250],
         title={"zh": "合併大師", "en": "Merge Master"},
         desc={"zh": "{v} 個 Pull Request 被合併", "en": "{v} pull requests merged"}),
    dict(id="voyager", icon="🧭", metric="external_prs_merged", unit="",
         thresholds=[1, 5, 20, 50],
         title={"zh": "開源旅人", "en": "Open Source Voyager"},
         desc={"zh": "在別人的專案合併了 {v} 個 PR", "en": "{v} PRs merged into others' projects"}),
    dict(id="gatekeeper", icon="🛡️", metric="reviews", unit="",
         thresholds=[5, 25, 100, 300],
         title={"zh": "守門人", "en": "Gatekeeper"},
         desc={"zh": "完成 {v} 次 Code Review", "en": "{v} code reviews"}),
    dict(id="bug_hunter", icon="🐞", metric="issues", unit="",
         thresholds=[5, 20, 50, 150],
         title={"zh": "除錯獵人", "en": "Bug Hunter"},
         desc={"zh": "開了 {v} 個 Issue", "en": "Opened {v} issues"}),
    dict(id="stargazer", icon="⭐", metric="stars_owned", unit="",
         thresholds=[10, 50, 250, 1000],
         title={"zh": "星光收集者", "en": "Stargazer"},
         desc={"zh": "活躍專案共獲得 {v} 顆星", "en": "{v} stars across active repos"}),
    dict(id="overdrive", icon="⚡", metric="busiest_day_count", unit="",
         thresholds=[10, 20, 40, 80],
         title={"zh": "爆肝日", "en": "Overdrive"},
         desc={"zh": "單日最高 {v} 次貢獻", "en": "{v} contributions in a single day"}),
    dict(id="night_owl", icon="🦉", metric="night_ratio", unit="%", min_sample=("sampled_commits", 20),
         thresholds=[10, 20, 35, 50],
         title={"zh": "夜貓子", "en": "Night Owl"},
         desc={"zh": "{v}% 的 commit 在午夜到清晨 5 點", "en": "{v}% of commits between 0–5 AM"}),
    dict(id="early_bird", icon="🐦", metric="morning_ratio", unit="%", min_sample=("sampled_commits", 20),
         thresholds=[10, 20, 35, 50],
         title={"zh": "晨型人", "en": "Early Bird"},
         desc={"zh": "{v}% 的 commit 在早上 5–9 點", "en": "{v}% of commits between 5–9 AM"}),
    dict(id="weekend_warrior", icon="🏕️", metric="weekend_ratio", unit="%",
         min_sample=("total_contributions", 50),
         thresholds=[20, 30, 40, 50],
         title={"zh": "週末戰士", "en": "Weekend Warrior"},
         desc={"zh": "{v}% 的貢獻發生在週末", "en": "{v}% of contributions on weekends"}),
    dict(id="perfect_month", icon="🗓️", metric="perfect_months", unit="",
         thresholds=[1, 3, 6, 12],
         title={"zh": "全勤月", "en": "Perfect Month"},
         desc={"zh": "{v} 個月每天都有貢獻", "en": "{v} months with no empty day"}),
    dict(id="deep_focus", icon="🎯", metric="top_repo_commits", unit="",
         thresholds=[50, 150, 400, 1000],
         title={"zh": "專注一擊", "en": "Deep Focus"},
         desc={"zh": "在單一專案提交 {v} 次", "en": "{v} commits to a single project"}),
    dict(id="multithreaded", icon="🧵", metric="repos_contributed", unit="",
         thresholds=[3, 8, 15, 30],
         title={"zh": "多線並行", "en": "Multi-threaded"},
         desc={"zh": "同時推進 {v} 個專案", "en": "Pushed code to {v} repositories"}),
    dict(id="all_seasons", icon="🍂", metric="active_months", unit="",
         thresholds=[6, 9, 11, 12],
         title={"zh": "四季不輟", "en": "All Seasons"},
         desc={"zh": "{v} 個月份都有產出", "en": "Active in {v} months"}),
    dict(id="shipper", icon="🚀", metric="releases", unit="",
         thresholds=[1, 5, 15, 40],
         title={"zh": "出貨達人", "en": "Shipper"},
         desc={"zh": "今年發佈了 {v} 個 Release", "en": "Published {v} releases"}),
]


def evaluate_achievements(stats: dict) -> list[dict]:
    out = []
    for a in ACHIEVEMENTS:
        value = stats.get(a["metric"]) or 0
        guard = a.get("min_sample")
        eligible = not guard or (stats.get(guard[0]) or 0) >= guard[1]
        tier_idx = -1
        if eligible:
            for i, t in enumerate(a["thresholds"]):
                if value >= t:
                    tier_idx = i
        nxt = a["thresholds"][tier_idx + 1] if tier_idx + 1 < len(a["thresholds"]) else None
        prev = a["thresholds"][tier_idx] if tier_idx >= 0 else 0
        progress = 1.0 if nxt is None else max(0.0, min(1.0, (value - prev) / (nxt - prev))) if nxt != prev else 1.0
        out.append({
            "id": a["id"], "icon": a["icon"], "metric": a["metric"], "unit": a["unit"],
            "title": a["title"], "desc": a["desc"],
            "value": round(value, 1) if isinstance(value, float) else value,
            "thresholds": a["thresholds"],
            "unlocked": tier_idx >= 0,
            "eligible": eligible,
            "tier": TIERS[tier_idx] if tier_idx >= 0 else None,
            "tier_index": tier_idx,
            "next_threshold": nxt,
            "progress_to_next": round(progress, 3),
        })
    out.sort(key=lambda x: (-x["tier_index"], -x["progress_to_next"]))
    return out


# ------------------------------------------------------------------ stats
def calendar_days(raw: dict) -> list[dict]:
    weeks = raw["contributions"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    year = raw["meta"]["year"]
    return sorted((d for d in days if d["date"].startswith(str(year))), key=lambda d: d["date"])


def streaks(days: list[dict]) -> dict:
    longest = cur = 0
    best_start = best_end = run_start = None
    for d in days:
        if d["contributionCount"] > 0:
            if cur == 0:
                run_start = d["date"]
            cur += 1
            if cur > longest:
                longest, best_start, best_end = cur, run_start, d["date"]
        else:
            cur = 0
    # current streak counted back from the last day (allow today to still be empty)
    current = 0
    for i, d in enumerate(reversed(days)):
        if d["contributionCount"] > 0:
            current += 1
        elif i == 0:
            continue
        else:
            break
    return {"longest": longest, "longest_start": best_start, "longest_end": best_end, "current": current}


def build(raw: dict, exclude_private: bool) -> dict:
    meta = raw["meta"]
    year = meta["year"]
    cc = raw["contributions"]
    days = calendar_days(raw)
    total = sum(d["contributionCount"] for d in days)

    # months / weekdays
    monthly = [0] * 12
    month_days: dict[int, list[int]] = collections.defaultdict(list)
    weekday = [0] * 7  # 0 = Sunday (GitHub convention)
    for d in days:
        m = int(d["date"][5:7]) - 1
        monthly[m] += d["contributionCount"]
        month_days[m].append(d["contributionCount"])
        weekday[d["weekday"]] += d["contributionCount"]
    perfect_months = 0
    for m, counts in month_days.items():
        if len(counts) == calendar.monthrange(year, m + 1)[1] and all(c > 0 for c in counts):
            perfect_months += 1
    busiest = max(days, key=lambda d: d["contributionCount"], default={"date": None, "contributionCount": 0})
    st = streaks(days)

    # hour-of-day from commit samples
    tz = None
    if ZoneInfo and meta.get("tz"):
        try:
            tz = ZoneInfo(meta["tz"])
        except Exception:  # noqa: BLE001
            print(f"[analyze] unknown tz {meta['tz']}, using UTC", file=sys.stderr)
    hours = [0] * 24
    sampled = 0
    for s in raw.get("commit_samples", []):
        for c in s["commits"]:
            t = dt.datetime.fromisoformat(c["date"].replace("Z", "+00:00"))
            if tz:
                t = t.astimezone(tz)
            hours[t.hour] += 1
            sampled += 1
    night = sum(hours[0:5])
    morning = sum(hours[5:9])
    peak_hour = max(range(24), key=lambda h: hours[h]) if sampled else None

    # projects
    start_iso = meta["range"]["from"]
    end_iso = meta["range"]["to"]
    by_repo = {x["repository"]["nameWithOwner"]: x for x in cc["commitContributionsByRepository"]}
    pr_by_repo = {x["repository"]["nameWithOwner"]: x["contributions"]["totalCount"]
                  for x in cc.get("pullRequestContributionsByRepository", [])}
    login = raw["profile"]["login"]
    owned = raw["owned_repositories"]["nodes"]
    repos: dict[str, dict] = {}
    for r in owned:
        if start_iso <= (r.get("createdAt") or "") < end_iso and not r.get("isFork"):
            repos[r["nameWithOwner"]] = {"repo": r, "commits": 0}
    for name, x in by_repo.items():
        repos.setdefault(name, {"repo": x["repository"], "commits": 0})["commits"] = x["contributions"]["totalCount"]

    lang_weight: collections.Counter = collections.Counter()
    lang_color: dict[str, str] = {}
    releases = 0
    projects = []
    for name, entry in repos.items():
        r, commits = entry["repo"], entry["commits"]
        langs = r.get("languages") or {}
        tot = langs.get("totalSize") or sum(e["size"] for e in langs.get("edges", [])) or 1
        lang_list = []
        for e in langs.get("edges", []):
            share = e["size"] / tot
            lang_list.append({"name": e["node"]["name"], "color": e["node"].get("color"), "share": round(share, 3)})
            if e["node"].get("color"):
                lang_color[e["node"]["name"]] = e["node"]["color"]
            lang_weight[e["node"]["name"]] += share * max(commits, 1)
        rel_this_year = [x for x in (r.get("releases") or {}).get("nodes", [])
                         if start_iso <= (x.get("publishedAt") or "") < end_iso]
        if r.get("owner", {}).get("login") == login:
            releases += len(rel_this_year)
        private = bool(r.get("isPrivate"))
        if exclude_private and private:
            display_name, desc, url = "🔒 Private project", None, None
        else:
            display_name, desc, url = r["name"], r.get("description"), r.get("url")
        projects.append({
            "id": name,
            "name": display_name,
            "full_name": None if (exclude_private and private) else name,
            "description": desc,
            "url": url,
            "homepage": None if (exclude_private and private) else r.get("homepageUrl"),
            "owner_is_user": r.get("owner", {}).get("login") == login,
            "is_new": start_iso <= (r.get("createdAt") or "") < end_iso,
            "is_private": private,
            "is_fork": bool(r.get("isFork")),
            "created_at": r.get("createdAt"),
            "pushed_at": r.get("pushedAt"),
            "stars": r.get("stargazerCount", 0),
            "forks": r.get("forkCount", 0),
            "commits": commits,
            "pull_requests": pr_by_repo.get(name, 0),
            "primary_language": (r.get("primaryLanguage") or {}).get("name"),
            "primary_color": (r.get("primaryLanguage") or {}).get("color"),
            "languages": lang_list[:5],
            "topics": [t["topic"]["name"] for t in (r.get("repositoryTopics") or {}).get("nodes", [])],
            "releases": [{"tag": x["tagName"], "name": x.get("name"), "date": x.get("publishedAt")}
                         for x in rel_this_year],
        })
    projects.sort(key=lambda p: (-p["commits"], -p["stars"]))

    lang_total = sum(lang_weight.values()) or 1
    languages = [{"name": n, "color": lang_color.get(n), "share": round(w / lang_total, 4)}
                 for n, w in lang_weight.most_common()]
    meaningful_langs = [l for l in languages if l["share"] >= 0.03]

    search = raw.get("search") or {}
    ext = search.get("mergedExternal") or {}
    external_prs = [n for n in ext.get("nodes", []) if n]

    stats = {
        "total_contributions": total,
        "commits": cc.get("totalCommitContributions", 0),
        "pull_requests": cc.get("totalPullRequestContributions", 0),
        "issues": cc.get("totalIssueContributions", 0),
        "reviews": cc.get("totalPullRequestReviewContributions", 0),
        "private_contributions": cc.get("restrictedContributionsCount", 0),
        "private_commits": sum(p["commits"] for p in projects if p["is_private"]),
        "private_repos_contributed": sum(1 for p in projects if p["is_private"] and p["commits"] > 0),
        "repos_created": sum(1 for p in projects if p["is_new"] and p["owner_is_user"]),
        "repos_contributed": max(cc.get("totalRepositoriesWithContributedCommits", 0),
                                 sum(1 for p in projects if p["commits"] > 0)),
        "prs_merged": (search.get("merged") or {}).get("issueCount", 0),
        "external_prs_merged": ext.get("issueCount", 0),
        "issues_closed": (search.get("issuesClosed") or {}).get("issueCount", 0),
        "active_days": sum(1 for d in days if d["contributionCount"] > 0),
        "days_in_range": len(days),
        "active_months": sum(1 for v in monthly if v > 0),
        "longest_streak": st["longest"],
        "longest_streak_start": st["longest_start"],
        "longest_streak_end": st["longest_end"],
        "current_streak": st["current"],
        "busiest_day": busiest["date"],
        "busiest_day_count": busiest["contributionCount"],
        "busiest_month": monthly.index(max(monthly)) + 1 if total else None,
        "perfect_months": perfect_months,
        "weekend_ratio": round(100 * (weekday[0] + weekday[6]) / total, 1) if total else 0,
        "sampled_commits": sampled,
        "night_ratio": round(100 * night / sampled, 1) if sampled else 0,
        "morning_ratio": round(100 * morning / sampled, 1) if sampled else 0,
        "peak_hour": peak_hour,
        "language_count": len(meaningful_langs),
        "top_language": languages[0]["name"] if languages else None,
        "stars_owned": sum(p["stars"] for p in projects if p["owner_is_user"]),
        "top_repo_commits": max((p["commits"] for p in projects), default=0),
        "releases": releases,
        "followers": raw["profile"].get("followers", {}).get("totalCount", 0),
    }

    private_names = {p["id"] for p in projects if p["is_private"]}
    return {
        "meta": meta,
        "profile": {k: raw["profile"].get(k) for k in ("login", "name", "avatarUrl", "bio", "url", "location", "company")},
        "stats": stats,
        "calendar": [{"date": d["date"], "count": d["contributionCount"], "weekday": d["weekday"]} for d in days],
        "monthly": monthly,
        "weekday": weekday,
        "hours": hours,
        "languages": languages[:10],
        # Removing the records also removes IDs, topics, release tags and timestamps.
        # Counts and achievements above still include private activity.
        "projects": [p for p in projects if not p["is_private"]] if exclude_private else projects,
        "external_prs": [] if exclude_private else external_prs[:20],
        "achievements": evaluate_achievements(stats),
        # Commit subjects for Claude to read when writing the narrative. Not rendered.
        # With --exclude-private only private repositories' subjects are dropped.
        "commit_messages": {
            s["repository"]: [c["message"] for c in s["commits"][:60]] for s in raw.get("commit_samples", [])
            if not (exclude_private and s["repository"] in private_names)
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw")
    ap.add_argument("-o", "--output", default="analysis.json")
    ap.add_argument("--exclude-private", action="store_true", help="omit private repo details while retaining aggregate activity")
    args = ap.parse_args()
    with open(args.raw, encoding="utf-8") as f:
        raw = json.load(f)
    result = build(raw, args.exclude_private)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    s = result["stats"]
    unlocked = [a for a in result["achievements"] if a["unlocked"]]
    print(f"[analyze] {s['total_contributions']} contributions, {s['active_days']} active days, "
          f"{len(result['projects'])} projects, {len(unlocked)}/{len(result['achievements'])} achievements unlocked",
          file=sys.stderr)
    print(f"[analyze] saved {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
