# 內建成就 / Built-in achievements

每個成就有 4 個門檻，對應四種稀有度：普通 → 稀有 → 史詩 → 傳說。

| | ID | 名稱 | Name | 指標 metric | 普通 | 稀有 | 史詩 | 傳說 |
|---|---|---|---|---|---|---|---|---|
| 🔥 | `eternal_flame` | 不滅之火 | Eternal Flame | `longest_streak` (days) | 7 | 30 | 100 | 200 |
| ⚒️ | `forged` | 千錘百鍊 | Forged in Commits | `total_contributions` | 100 | 500 | 1000 | 3000 |
| 📅 | `daily_builder` | 日更職人 | Daily Builder | `active_days` (days) | 50 | 100 | 200 | 300 |
| 🌱 | `genesis` | 創世者 | Genesis | `repos_created` | 1 | 5 | 10 | 20 |
| 🗣️ | `polyglot` | 多語通 | Polyglot | `language_count` | 2 | 4 | 6 | 8 |
| 🔀 | `merge_master` | 合併大師 | Merge Master | `prs_merged` | 5 | 25 | 100 | 250 |
| 🧭 | `voyager` | 開源旅人 | Open Source Voyager | `external_prs_merged` | 1 | 5 | 20 | 50 |
| 🛡️ | `gatekeeper` | 守門人 | Gatekeeper | `reviews` | 5 | 25 | 100 | 300 |
| 🐞 | `bug_hunter` | 除錯獵人 | Bug Hunter | `issues` | 5 | 20 | 50 | 150 |
| ⭐ | `stargazer` | 星光收集者 | Stargazer | `stars_owned` | 10 | 50 | 250 | 1000 |
| ⚡ | `overdrive` | 爆肝日 | Overdrive | `busiest_day_count` | 10 | 20 | 40 | 80 |
| 🦉 | `night_owl` | 夜貓子 | Night Owl | `night_ratio` (%) | 10 | 20 | 35 | 50 |
| 🐦 | `early_bird` | 晨型人 | Early Bird | `morning_ratio` (%) | 10 | 20 | 35 | 50 |
| 🏕️ | `weekend_warrior` | 週末戰士 | Weekend Warrior | `weekend_ratio` (%) | 20 | 30 | 40 | 50 |
| 🗓️ | `perfect_month` | 全勤月 | Perfect Month | `perfect_months` | 1 | 3 | 6 | 12 |
| 🎯 | `deep_focus` | 專注一擊 | Deep Focus | `top_repo_commits` | 50 | 150 | 400 | 1000 |
| 🧵 | `multithreaded` | 多線並行 | Multi-threaded | `repos_contributed` | 3 | 8 | 15 | 30 |
| 🍂 | `all_seasons` | 四季不輟 | All Seasons | `active_months` | 6 | 9 | 11 | 12 |
| 🚀 | `shipper` | 出貨達人 | Shipper | `releases` | 1 | 5 | 15 | 40 |

## 指標說明

- `longest_streak`：連續有貢獻的最長天數（依 GitHub 貢獻日曆）
- `total_contributions`：貢獻日曆的總和（commit、PR、issue、review 等）
- `active_days` / `active_months`：有任何貢獻的天數 / 月份數
- `repos_created`：今年由你建立（非 fork）的 repo 數
- `language_count`：依 commit 加權後佔比 ≥ 3% 的語言數
- `prs_merged` / `external_prs_merged`：今年被合併的 PR / 合併進非自己帳號 repo 的 PR
- `reviews` / `issues`：Code Review 與開 Issue 次數
- `stars_owned`：今年活躍或新建、且屬於你的 repo 的星星總數
- `busiest_day_count`：單日最高貢獻數
- `night_ratio` / `morning_ratio`：抽樣 commit 中 0–5 點 / 5–9 點的比例（需 ≥ 20 個樣本，依 `--tz` 時區）
- `weekend_ratio`：週末貢獻比例（需總貢獻 ≥ 50）
- `perfect_months`：完整月份中每天都有貢獻的月份數
- `top_repo_commits`：單一 repo 最多的 commit 數
- `repos_contributed`：今年有 commit 的 repo 數
- `releases`：自己 repo 今年發佈的 Release 數（每個 repo 最多取 5 筆）

想新增或調整成就：編輯 `scripts/analyze.py` 內的 `ACHIEVEMENTS` 清單即可。
需要依質性證據頒發的成就（例如「首次上線產品」），由 Claude 寫在 `narrative.json` 的 `custom_achievements`。
