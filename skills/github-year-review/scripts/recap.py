#!/usr/bin/env python3
"""RecapLion one-shot CLI: fetch -> analyze -> render in a single command.

Works for anyone, with or without an AI agent:

  python3 recap.py --user octocat                       # current year, English
  python3 recap.py --user octocat --year 2026 --tz Asia/Taipei --lang zh
  python3 recap.py --user octocat --narrative narrative.json --skip-fetch   # re-render after writing a story

Outputs go to ./recap-<user>-<year>/ (override with --out):
  raw.json, analysis.json, year-review.html, cards/*.svg
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script: str, *args: str) -> None:
    cmd = [sys.executable, os.path.join(HERE, script), *args]
    display = list(cmd)
    if "--token" in display:
        display[display.index("--token") + 1] = "[redacted]"
    print(f"$ {' '.join(display)}", file=sys.stderr)
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True, help="GitHub login")
    ap.add_argument("--year", type=int, default=dt.date.today().year)
    ap.add_argument("--tz", default="UTC", help="IANA timezone, e.g. Asia/Taipei, America/New_York")
    ap.add_argument("--lang", choices=["en", "zh"], default=None,
                    help="page language (default: narrative.lang, else en)")
    ap.add_argument("--out", help="output directory (default: recap-<user>-<year>)")
    ap.add_argument("--narrative", help="optional narrative.json (story, project notes, special achievements)")
    ap.add_argument("--include-private", action="store_true", help="also collect the authenticated account's private activity")
    ap.add_argument("--exclude-private", action="store_true", help="omit private repo details from the report, preserving aggregate activity")
    ap.add_argument("--source", choices=["auto", "graphql", "search", "rest"], default="auto")
    ap.add_argument("--token", help="GitHub token (else GITHUB_TOKEN / GH_TOKEN / gh auth token)")
    ap.add_argument("--skip-fetch", action="store_true", help="reuse an existing raw.json in --out")
    ap.add_argument("--no-cards", action="store_true", help="skip SVG achievement cards")
    args = ap.parse_args()

    out = args.out or f"recap-{args.user}-{args.year}"
    os.makedirs(out, mode=0o700 if args.include_private else 0o777, exist_ok=True)
    raw = os.path.join(out, "raw.json")
    analysis = os.path.join(out, "analysis.json")

    if args.skip_fetch and args.include_private and os.path.exists(raw):
        with open(raw, encoding="utf-8") as cached:
            cached_meta = json.load(cached).get("meta", {})
            if not cached_meta.get("include_private"):
                ap.error("cached raw.json was not collected with --include-private; rerun without --skip-fetch")
            if (cached_meta.get("user", "").lower() != args.user.lower()
                    or cached_meta.get("year") != args.year):
                ap.error("private cache belongs to a different account or year; rerun without --skip-fetch")
    if not (args.skip_fetch and os.path.exists(raw)):
        fetch = ["--user", args.user, "--year", str(args.year), "--tz", args.tz, "--source", args.source, "-o", raw]
        if args.token:
            fetch += ["--token", args.token]
        if args.include_private:
            fetch += ["--include-private"]
        run("fetch_github_year.py", *fetch)

    run("analyze.py", raw, "-o", analysis, *(["--exclude-private"] if args.exclude_private else []))

    render = [analysis, "-o", os.path.join(out, "year-review.html")]
    if args.narrative:
        render += ["--narrative", args.narrative]
    if not args.no_cards:
        render += ["--cards-dir", os.path.join(out, "cards")]
    if args.lang:
        render += ["--lang", args.lang]
    run("render.py", *render)

    print(f"\nDone → {os.path.join(out, 'year-review.html')}", file=sys.stderr)
    if not args.narrative:
        print("Tip: write a narrative.json (see references/narrative-schema.md) and re-run with "
              "--narrative narrative.json --skip-fetch for project stories and special achievements.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
