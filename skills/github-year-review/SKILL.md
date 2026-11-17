---
name: github-year-review
description: Generate an animated GitHub "year in review" for a user — yearly stats, contribution heatmap, the projects/systems they built, and tiered achievement cards (HTML page with animations + animated SVG cards for a profile README). Use when the user asks to review their year on GitHub, recap their repos/projects, make a GitHub wrapped / 年度回顧 / 成就卡, or summarize what they built or achieved this year.
---

# RecapLion — GitHub Year Review（GitHub 年度回顧）

Produce a personal, animated year-in-review for a GitHub user:

- `year-review.html` — single self-contained page: hero intro, count-up stats, animated heatmap,
  monthly / hour-of-day charts, language map, project cards, flip-able achievement cards
  (common → rare → epic → legendary, holo + confetti), next-goal progress bars.
- `cards/*.svg` — one animated SVG card per unlocked achievement plus `summary.svg`,
  embeddable in a GitHub profile README.

The scripts do the data work; **your job is the narrative**: reading what the projects actually are
and writing the headline, project taglines/highlights and special achievements.

All scripts are Python 3 standard library only. Paths below are relative to this skill directory.

## Workflow

### 1. Gather inputs
Determine (ask only if you cannot infer):
- **GitHub login** — from the request, `git config user.name`, `gh api user`, or the repo remote.
- **Year** — default: the current year (the range ends today if the year is not over).
- **Timezone** — for night-owl / early-bird stats (e.g. `Asia/Taipei`). Infer from context; default `UTC`.
- **Language** — `zh` (Traditional Chinese, default) or `en`. Match the user's language.
- **Private repos** — if the page will be shared publicly, use `--exclude-private`.

Work in a scratch/output directory, e.g. `./year-review-<login>-<year>/`.

### 2. Fetch data
```bash
python3 scripts/fetch_github_year.py --user <login> --year <year> --tz <tz> -o raw.json
```
Token lookup: `--token`, `GITHUB_TOKEN`/`GH_TOKEN`, then `gh auth token`. A token gives the full
GraphQL data (calendar, PRs, reviews, private contribution counts). If there is no token or GraphQL
is unreachable (e.g. sandboxed sessions), it falls back to the public **search API**
(`--source search`): commits, PRs, issues and repos are collected from search results and the
calendar is rebuilt from their dates. It takes a few minutes because of search rate limits
(it sleeps and retries automatically). Tell the user this mode covers public activity only, and
that reviews are approximate and releases unknown.

### 3. Analyze
```bash
python3 scripts/analyze.py raw.json -o analysis.json [--exclude-private]
```
This computes stats, the project list, the language mix and evaluates the 19 built-in
achievements (see `references/achievements.md`).

### 4. Understand the projects and write the narrative  ← the important part
Read `analysis.json` (`stats`, `projects`, `achievements`, `commit_messages`). For the top
projects (by commits, stars, or being new this year — up to ~8), learn what they are:
- read the README (if reachable) via `gh api repos/<owner>/<repo>/readme -H "Accept: application/vnd.github.raw"`,
  the GitHub MCP `get_file_contents` tool, or a local clone if present;
- use the commit subjects in `commit_messages` to see what was actually built this year — in
  search mode every public commit is there, which is usually enough even without READMEs.

Then write `narrative.json` (schema in `references/narrative-schema.md`, full example in
`../../examples/sample/narrative.json`):
- `headline` — one sentence capturing the year's story (typed out in the hero).
- `theme_words` — 3–6 chips (tech, domains, themes).
- `projects` — per repo: `category` (e.g. AI 系統 / 基礎設施 / 工具 / 網站 / App),
  a `tagline`, and 1–3 concrete `highlights` grounded in README/commits.
- `project_order` — optional curated order (most meaningful first).
- `custom_achievements` — 1–4 **special** achievements you award from qualitative evidence the
  metrics can't see (first product launch, built a DB from scratch, first contribution to a big OSS
  project, migrated a system to a new stack…). Each needs `id, icon, tier, title, desc, detail`.
  Only award what the evidence supports; never invent facts or numbers.
- `achievements` — optional flavor text per built-in achievement id (shown on the card back).
- `summary` and `closing` — 2–4 warm, specific sentences each.

Keep the tone celebratory but honest. Do not mention private repo names if `--exclude-private`
was used.

### 5. Render
```bash
python3 scripts/render.py analysis.json --narrative narrative.json \
  -o year-review.html --cards-dir cards --lang zh
```
Open/preview the HTML if a browser is available (Playwright screenshot is a good check). Tell the
user where the files are, list the unlocked achievements (tier + title), the top projects, and the
nearest next goals.

### 6. Optional extras
- **Profile README**: suggest copying `cards/` into their `<login>/<login>` repo and embedding:
  ```md
  ![2026 GitHub Year in Review](./cards/summary.svg)
  <img src="./cards/eternal_flame.svg" width="200"> <img src="./cards/genesis.svg" width="200">
  ```
- **Publishing**: the HTML is self-contained (no external requests except the avatar image), so it
  can be hosted on GitHub Pages or shared as a file.

## Trying it without a token
```bash
python3 ../../examples/make_sample_raw.py -o raw.json   # fictional demo user
```
then continue from step 3.

## Notes
- `commit_messages` stays in `analysis.json` for you to read; `render.py` strips it from the page.
- The contribution calendar comes from GitHub and includes private contributions only if the user
  enabled "include private contributions" on their profile (or the token can see them).
- The page honours `prefers-reduced-motion` and has light/dark themes.
