---
name: github-year-review
description: Generate an animated GitHub "year in review" (RecapLion) for any GitHub user — yearly stats, contribution heatmap, the projects/systems they built, and tiered achievement cards (an animated HTML page plus animated SVG cards for a profile README). Use when the user asks to review or recap their year on GitHub, summarize what they built or achieved, make a "GitHub wrapped", 年度回顧, or 成就卡.
license: MIT
compatibility: Requires Python 3.9+ (standard library only) and HTTPS access to api.github.com. Works with any agent that can run shell commands (Claude Code, Codex, Gemini CLI, GitHub Copilot, Cursor, etc.).
metadata:
  project: RecapLion
  repository: https://github.com/malilion/RecapLion
---

# RecapLion — GitHub Year in Review

Produce a personal, animated year-in-review for any GitHub user:

- `year-review.html` — one self-contained page: intro animation, count-up stats, animated heatmap,
  monthly / hour-of-day charts, language map, project cards, flip-able achievement cards
  (common → rare → epic → legendary, holo + confetti) and next-goal progress bars.
- `cards/*.svg` — an animated SVG card per unlocked achievement plus `summary.svg`, embeddable in a
  GitHub profile README.

The scripts do the data work. **Your job as the agent is the story**: understand what the projects
actually are and write the headline, project notes and special achievements.

All paths below are relative to this skill's directory. Scripts use only the Python standard library.

## Workflow

### 1. Gather inputs
Infer these; ask the user only when you cannot:
- **GitHub login** — from the request, `gh api user -q .login`, `git config user.name`, or a remote URL.
- **Year** — default the current year (the range ends today if the year is not over).
- **Timezone** — IANA name used for night-owl / early-bird stats (e.g. `Asia/Taipei`,
  `Europe/Berlin`). Default `UTC`.
- **Language** — `en` or `zh` (Traditional Chinese). Match the language the user writes in.
- **Sharing** — if the page will be public, add `--exclude-private`.

### 2. Fetch, analyze and render a first draft
```bash
python3 scripts/recap.py --user <login> --year <year> --tz <tz> --lang <en|zh> --out recap-<login>-<year>
```
This runs `fetch_github_year.py` → `analyze.py` → `render.py` and writes `raw.json`,
`analysis.json`, `year-review.html` and `cards/` into the output folder.

Data sources (`--source auto` picks the best available):
- **GraphQL** — used when a token is available (`--token`, `GITHUB_TOKEN`/`GH_TOKEN`, or
  `gh auth token`). Full data: calendar, PRs, reviews, releases, private contribution counts.
- **Search API** — automatic fallback with no token or when GraphQL is blocked. Public activity
  only; reviews are approximate and releases unknown. It can take a few minutes because of search
  rate limits (the script waits and retries by itself). Tell the user about these limits.

### 3. Understand the projects
Read `analysis.json`: `stats`, `projects`, `achievements`, and `commit_messages` (commit subjects
per repo, never published in the page). For the top projects (most commits, most stars, or new
this year — about 8–12):
- read each README if you can reach it (`gh api repos/<owner>/<repo>/readme -H "Accept: application/vnd.github.raw"`,
  a GitHub tool or MCP server, or a local clone);
- use the commit subjects to see what was actually built this year. They are often enough on
  their own.

### 4. Write `narrative.json`
Schema: `references/narrative-schema.md`. Full example: `references/example-narrative.json`.
- `headline` — one sentence that tells the year's story (typed out in the intro).
- `theme_words` — 3–6 chips (technologies, domains, themes).
- `projects` — per repo id: `category`, `tagline`, 1–3 concrete `highlights`.
- `project_order` — curated order, most meaningful first.
- `custom_achievements` — 1–5 **special** achievements earned from evidence the metrics can't see
  (first product launch, built a database from scratch, a family of related products, shipped on a
  new platform…). Each needs `id, icon, tier, title, desc, detail`.
- `achievements` — optional flavor text keyed by built-in achievement id (shown on the card back).
- `summary`, `closing` — 2–4 warm, specific sentences each.

Rules: every fact and number must come from the data, READMEs or commits — never invent. Verify
numbers you quote against `analysis.json`. Celebrate, but stay honest. Do not name private repos
if `--exclude-private` was used. Text fields may be bilingual: `{"en": "...", "zh": "..."}`.

### 5. Re-render with the story
```bash
python3 scripts/recap.py --user <login> --year <year> --lang <en|zh> --out recap-<login>-<year> \
  --narrative recap-<login>-<year>/narrative.json --skip-fetch
```
If you can, open or screenshot the HTML to check it. Then report: where the files are, the headline
numbers, unlocked achievements (tier + title), top projects and the nearest next goals, plus any
data limitations.

### 6. Optional extras
- **Profile README** — copy `cards/` into the user's `<login>/<login>` repository and embed:
  ```md
  ![Year in review](./cards/summary.svg)
  <img src="./cards/eternal_flame.svg" width="200"> <img src="./cards/genesis.svg" width="200">
  ```
- **Hosting** — the HTML is self-contained (only the avatar is loaded remotely); it works on
  GitHub Pages or as a plain file.

## Individual scripts
| Script | Purpose |
|---|---|
| `scripts/fetch_github_year.py` | Collect raw yearly data (`--source auto|graphql|search|rest`) |
| `scripts/analyze.py` | Stats, projects, languages, achievement evaluation |
| `scripts/render.py` | HTML page + SVG cards (`--narrative`, `--lang`, `--cards-dir`) |
| `scripts/recap.py` | All of the above in one command |
| `scripts/make_sample_raw.py` | Fictional demo data for trying it without network access |

Achievement thresholds: `references/achievements.md`. To add one, edit `ACHIEVEMENTS` in
`scripts/analyze.py`.
