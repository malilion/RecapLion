# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, Gemini CLI, GitHub Copilot, Cursor, and others).

## What this repository is
**RecapLion** generates an animated GitHub year-in-review — stats, heatmap, project cards and tiered
achievement cards — for any GitHub user. It is packaged as an [Agent Skill](https://agentskills.io)
in `skills/github-year-review/`.

## If a user asks you for a GitHub year in review
Follow `skills/github-year-review/SKILL.md`. In short:

1. Run `python3 skills/github-year-review/scripts/recap.py --user <login> --year <year> --tz <tz> --lang <en|zh>`.
2. Read `recap-<login>-<year>/analysis.json` (especially `projects` and `commit_messages`) and the
   READMEs of the top projects.
3. Write `recap-<login>-<year>/narrative.json` following
   `skills/github-year-review/references/narrative-schema.md`. Ground every fact in the data.
4. Re-run with `--narrative recap-<login>-<year>/narrative.json --skip-fetch`.

## Working on the code
- Python 3.9+, standard library only. Keep it dependency-free.
- `scripts/fetch_github_year.py` (GraphQL) and `scripts/search_source.py` (search API fallback)
  must produce the same raw structure.
- The page template is `assets/report_template.html`: a single file, no external scripts, honours
  `prefers-reduced-motion`, works at phone width. UI strings live in its `T` dictionary (`zh`, `en`).
- Quick check without network access:
  ```bash
  cd skills/github-year-review
  python3 scripts/make_sample_raw.py -o /tmp/raw.json
  python3 scripts/analyze.py /tmp/raw.json -o /tmp/analysis.json
  python3 scripts/render.py /tmp/analysis.json --narrative references/example-narrative.json -o /tmp/r.html --cards-dir /tmp/cards
  ```
