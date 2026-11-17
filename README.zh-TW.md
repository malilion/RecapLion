<div align="center">

<img src="docs/brand/icon.svg" width="128" height="128" alt="RecapLion 圖示">

# RecapLion 回顧獅

**任何人都能用、任何 AI agent 都能跑的 GitHub 年度回顧。**

[English](README.md) · **繁體中文**

[🌐 介紹網頁與線上 Demo](https://malilion.github.io/RecapLion/?lang=zh)

[🦁 malilion 的 2026 真實年度回顧](https://malilion.github.io/RecapLion/demo/malilion-2026/)

</div>

RecapLion 會回顧你今年在 GitHub 做了哪些專案與系統、達成了哪些成就，產生一個**有動畫的年度回顧網頁**，
以及可以放進個人頁的**動畫成就卡**。

![hero](docs/hero.png)

## ✨ 功能

- **年度數字**：總貢獻、commits、PR、code review、活躍天數、最長連續天數，數字會滾動跑出來
- **熱力圖與圖表**：一格一格浮現的貢獻熱力圖、每月長條圖、commit 時段時鐘圖
- **語言版圖**：依你在每個專案的 commit 量加權
- **年度專案卡**：agent 會讀 README 與 commit 紀錄，替每個專案寫分類、一句話介紹和重點
- **成就卡**：19 種內建成就 × 4 種稀有度（普通／稀有／史詩／傳說），發牌翻面、3D 傾斜、全息閃光、傳說級發光邊框與彩帶
- **特別成就**：agent 根據專案內容頒發數據看不出來的成就，例如「從零造資料庫」「全平台出貨」
- **下一個目標**：快要解鎖的成就與進度條
- **動畫 SVG 成就卡**：每個成就一張，另有年度總結卡，可以直接放進 GitHub 個人頁
- 繁體中文與英文、單一 HTML 檔、亮暗主題、手機版排版、支援 `prefers-reduced-motion`
- **只用 Python 標準函式庫**：不必 `pip install`，也不需要 Node

| 熱力圖與圖表 | 年度專案 |
|---|---|
| ![heat](docs/heat.png) | ![projects](docs/projects.png) |

![achievements](docs/achievements.png)

<p>
<img src="examples/sample/cards/first_400_stars.svg" width="200">
<img src="examples/sample/cards/stargazer.svg" width="200">
<img src="examples/sample/cards/night_owl.svg" width="200">
<img src="examples/sample/cards/genesis.svg" width="200">
</p>

![summary](examples/sample/cards/summary.svg)

## 🤖 支援的 AI agent

RecapLion 採用開放的 [Agent Skills](https://agentskills.io) 格式（一個含 `SKILL.md` 的資料夾），
Claude Code、OpenAI Codex、Gemini CLI、GitHub Copilot、Cursor 等 agent 都能使用。
repo 另外附上 [`AGENTS.md`](AGENTS.md)，給讀取這個檔案的 agent。

### 安裝

**一鍵安裝（任何 agent，自動偵測）**

```bash
curl -fsSL https://raw.githubusercontent.com/malilion/RecapLion/main/install.sh | sh
```

會自動偵測 Claude Code（`~/.claude/skills`）與 Codex／其他支援 Agent Skills 的工具（`~/.agents/skills`）。
也可以指定目標或任意資料夾：

```bash
sh install.sh claude codex
```

```bash
sh install.sh --dir ~/path/to/your/agent/skills
```

**Claude Code plugin**

```
/plugin marketplace add malilion/RecapLion
```

```
/plugin install recaplion@recaplion
```

**Skills CLI**（如果你有在用）

```bash
npx skills add malilion/RecapLion
```

**手動安裝**：把 `skills/github-year-review/` 整個資料夾複製到 agent 的 skills 資料夾即可，它不依賴 repo 其他檔案。

### 使用

對 agent 說：

> 幫我做 2026 年的 GitHub 年度回顧，帳號是 `octocat`，時區 Asia/Taipei，要有成就卡。

agent 會執行腳本、閱讀你的專案、寫出年度故事與特別成就，再產生網頁。完整流程見
[`SKILL.md`](skills/github-year-review/SKILL.md)。

## 🧑‍💻 不用 AI 也能跑

```bash
git clone https://github.com/malilion/RecapLion.git
```

```bash
python3 RecapLion/skills/github-year-review/scripts/recap.py --user <你的帳號> --tz Asia/Taipei --lang zh
```

執行時會先問你要涵蓋哪些 repo（也可以直接加 `--scope` 跳過提問）：

| 選擇 | 涵蓋範圍 | 需要 |
|---|---|---|
| `--scope public` | 只有公開 repo，完全不含私人資料（連匿名的數字都沒有），可以放心分享 | 不需要；有 token 會更快、更完整 |
| `--scope all` | 公開 **加上** 你自己的私人 repo | 同一個帳號的 GitHub token（`gh auth login`） |

打開 `recap-<帳號>-<年份>/year-review.html` 即可，所有統計、圖表與內建成就都會有。
想加上專案故事與特別成就，可以自己或請任何 AI 寫一份
[`narrative.json`](skills/github-year-review/references/narrative-schema.md)，
再加上 `--narrative narrative.json --skip-fetch` 重跑。

### GitHub token

讀取順序是 `--token`、`GITHUB_TOKEN` / `GH_TOKEN`、`gh auth token`，最簡單是先執行 `gh auth login`。
`--scope public` 有 token 時會用 GraphQL 取得精確資料，並過濾成只剩公開 repo；
沒有 token 時改用公開的 Search API，因為速率限制需要幾分鐘，review 數為估計值，也拿不到 release。

### 納入私人 repo（`--scope all`）

```bash
python3 RecapLion/skills/github-year-review/scripts/recap.py --user <你的帳號> --tz Asia/Taipei --lang zh --scope all
```

Token 的帳號須與 `--user` 相同，且有權讀取要計算的私人 repo。此模式會逐頁收集 repo 清單、
私人 repo 預設分支上的本人 commit、本人建立的 PR／Issue 與 Review。若 GitHub 日曆漏掉私人活動，
就補算後合併，並在報告標明統計方式；日曆已含的活動不會重複加總。收集失敗會直接報錯，
不會悄悄改成只有公開資料的回顧。

這份報告是給你自己看的。要分享時加上 `--exclude-private`：私人活動仍計入總數、圖表與成就，
但不會輸出私人 repo 的名稱、描述與 commit 訊息。`raw.json` 和 `analysis.json` 要保密；
自訂的年度故事等文字不會自動遮罩，分享前請自己確認。`--skip-fetch` 不會混用範圍：
公開模式會拒絕使用含私人資料的快取。涵蓋範圍與取樣限制見 [`SKILL.md`](skills/github-year-review/SKILL.md)。

### 自動更新個人頁

把 [`examples/github-action/recaplion.yml`](examples/github-action/recaplion.yml) 放進你的個人頁 repo
（`<你>/<你>`）的 `.github/workflows/`，每週會自動重新產生成就卡，
在 README 用 `![Year in review](./recap/cards/summary.svg)` 嵌入即可。

### 先看範例

```bash
cd RecapLion/skills/github-year-review
python3 scripts/make_sample_raw.py -o /tmp/raw.json
python3 scripts/analyze.py /tmp/raw.json -o /tmp/analysis.json
python3 scripts/render.py /tmp/analysis.json --narrative references/example-narrative.json -o /tmp/year-review.html --cards-dir /tmp/cards
```

或直接打開 [`examples/sample/year-review.html`](examples/sample/year-review.html)（虛構使用者 `demo-dev` 的範例）。

## 🏅 成就一覽

完整門檻見 [`references/achievements.md`](skills/github-year-review/references/achievements.md)。
想新增成就，編輯 `scripts/analyze.py` 裡的 `ACHIEVEMENTS` 清單即可。

| | 成就 | 條件 |
|---|---|---|
| 🔥 | 不滅之火 | 最長連續貢獻天數 |
| ⚒️ | 千錘百鍊 | 年度總貢獻 |
| 📅 | 日更職人 | 活躍天數 |
| 🌱 | 創世者 | 今年新建的 repo |
| 🗣️ | 多語通 | 使用的程式語言數 |
| 🔀 | 合併大師 | 被合併的 PR |
| 🧭 | 開源旅人 | 合併進別人專案的 PR |
| 🛡️ | 守門人 | Code Review 次數 |
| 🐞 | 除錯獵人 | 開 Issue 次數 |
| ⭐ | 星光收集者 | 自己專案的星星數 |
| ⚡ | 爆肝日 | 單日最高貢獻 |
| 🦉 | 夜貓子 | 凌晨 0–5 點 commit 比例 |
| 🐦 | 晨型人 | 早上 5–9 點 commit 比例 |
| 🏕️ | 週末戰士 | 週末貢獻比例 |
| 🗓️ | 全勤月 | 每天都有貢獻的月份 |
| 🎯 | 專注一擊 | 單一專案 commit 數 |
| 🧵 | 多線並行 | 有 commit 的 repo 數 |
| 🍂 | 四季不輟 | 有產出的月份數 |
| 🚀 | 出貨達人 | 發佈的 Release 數 |

## ❓ 常見問題

### 別人裝了這個 skill，會把全部（包含私人 repo）都抓走嗎？

不會。預設**不會**抓私人資料，而且無論怎麼設定，都**不可能**抓到別人的私人 repo。

**1. 跑的時候會先問使用者**

| 怎麼用 | 行為 |
|---|---|
| 透過 AI agent（Claude Code、Codex…） | `SKILL.md` 規定 agent 要先問「只看公開，還是連私人一起？」，使用者回答後才開始抓 |
| 自己在終端機跑 `recap.py` | 跳出選單讓你選 1（公開）或 2（全部） |
| 自動化環境（GitHub Action、CI） | 沒辦法問人，所以預設**只抓公開**；Action 範本也是 `RECAP_SCOPE: public` |

**2. 「全部」只能看自己的帳號**
- `--scope all` 要求 token 的擁有者必須就是 `--user`，程式會檢查，不符合就直接報錯。
- 所以別人用 RecapLion 查 `malilion`，只能看到 malilion 的公開 repo，私人 repo 永遠拿不到，因為他們沒有 malilion 的 token。
- 反過來也一樣：每個人選「全部」時，抓到的只有**他自己**有權限的私人 repo。

**3. 資料只留在自己電腦上**
- RecapLion 只會連到 GitHub 的 API，不會把任何資料傳給作者或其他伺服器。
- 產生的報告都存在使用者自己的資料夾，要不要分享由自己決定。

### 下載 skill 時會拿到哪些檔案？

- **用 `install.sh` 或手動複製：** 只會拿到 `skills/github-year-review/` 這個資料夾，裡面是程式和說明，沒有任何人的資料。
- **用 Claude Code 的 `/plugin install`：** 會下載整個 repo，包含 `docs/` 裡的網站和 Demo 報告。這些本來就公開在網站上，而且只有公開 repo。

### 選「只看公開」時，私人的活動也不會算進總數嗎？

對。`--scope public` 會完全排除私人活動，連貢獻日曆上的匿名數字都不算。（用自己的 token 時，GitHub
本身會把私人活動算進去，所以 RecapLion 會改用公開的貢獻紀錄重新計算整年。）

## 📁 結構

```
skills/github-year-review/      Agent Skill 本體（可單獨複製使用）
  SKILL.md                      給 agent 的執行流程
  scripts/
    recap.py                    一鍵指令：抓資料 → 分析 → 產生
    fetch_github_year.py        GraphQL 資料來源
    public_source.py            只含公開 repo 的 GraphQL 資料（--scope public）
    search_source.py            Search API 資料來源（不需 token）
    analyze.py                  統計與成就判定
    render.py                   產生 HTML 與 SVG 卡片
    make_sample_raw.py          虛構範例資料
  assets/report_template.html   動畫網頁模板
  references/                   成就門檻、narrative 格式與範例
AGENTS.md                       給 AI coding agent 的說明
install.sh                      安裝到 Claude Code／Codex／任意 skills 資料夾
.claude-plugin/                 Claude Code plugin 與 marketplace 設定
examples/                       範例產出、GitHub Action
```

## 授權

MIT © malilion
