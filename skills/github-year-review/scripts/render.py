#!/usr/bin/env python3
"""Render analysis.json (+ optional narrative.json) into:
  * an animated, self-contained HTML year-in-review page
  * optional animated SVG achievement cards (embeddable in a GitHub profile README)

Usage:
  python3 render.py analysis.json --narrative narrative.json -o year-review.html \
      --cards-dir cards --lang zh
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "report_template.html")

TIER_COLORS = {
    "common": ("#a3adc2", "#2a2f3d"),
    "rare": ("#3b9bff", "#0f2440"),
    "epic": ("#b46cff", "#2a1245"),
    "legendary": ("#ffb020", "#3d2600"),
}
TIER_LABEL = {
    "zh": {"common": "普通", "rare": "稀有", "epic": "史詩", "legendary": "傳說"},
    "en": {"common": "COMMON", "rare": "RARE", "epic": "EPIC", "legendary": "LEGENDARY"},
}


def tr(v, lang):
    if isinstance(v, dict):
        return v.get(lang) or v.get("zh") or v.get("en") or ""
    return v or ""


# ------------------------------------------------------------------ HTML
def render_html(data: dict, lang: str) -> str:
    with open(TEMPLATE, encoding="utf-8") as f:
        tpl = f.read()
    payload = dict(data)
    payload.pop("commit_messages", None)  # internal only, never published
    payload["lang"] = lang
    blob = json.dumps(payload, ensure_ascii=False)
    # keep the JSON inert inside <script>
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    name = data["profile"].get("name") or data["profile"]["login"]
    year = data["meta"]["year"]
    title = f"{name} · {year} GitHub 年度回顧" if lang == "zh" else f"{name} · GitHub {year} in Review"
    return (tpl.replace("__DATA__", blob)
               .replace("__TITLE__", html.escape(title))
               .replace("__LANG__", "zh-Hant" if lang == "zh" else "en"))


# ------------------------------------------------------------------ SVG cards
def svg_card(a: dict, year: int, login: str, lang: str) -> str:
    tier = a.get("tier") or "common"
    fg, bg = TIER_COLORS.get(tier, TIER_COLORS["common"])
    title = html.escape(tr(a["title"], lang))
    value = a.get("value")
    desc_raw = tr(a.get("desc"), lang)
    desc = html.escape(desc_raw.replace("{v}", f"{value:,}" if isinstance(value, (int, float)) else str(value or "")))
    tier_idx = ["common", "rare", "epic", "legendary"].index(tier) if tier in TIER_COLORS else 0
    pips = "".join(
        f'<rect x="{108 + i * 30}" y="300" width="24" height="5" rx="2.5" fill="{fg if i <= tier_idx else "#ffffff22"}"/>'
        for i in range(4))
    holo = ""
    if tier in ("epic", "legendary"):
        holo = '''<rect width="300" height="420" rx="22" fill="url(#holo)" opacity=".14" style="mix-blend-mode:screen"><animate attributeName="x" values="-300;300" dur="5s" repeatCount="indefinite"/></rect>'''
    glow = ""
    if tier == "legendary":
        glow = f'<rect x="3" y="3" width="294" height="414" rx="21" fill="none" stroke="{fg}" stroke-width="3" opacity=".9"><animate attributeName="opacity" values=".35;1;.35" dur="2.4s" repeatCount="indefinite"/></rect>'
    font = "'Inter','Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="420" viewBox="0 0 300 420" role="img" aria-label="{title}">
<defs>
  <radialGradient id="bg" cx="50%" cy="0%" r="110%"><stop offset="0" stop-color="{fg}" stop-opacity=".45"/><stop offset=".6" stop-color="{bg}"/><stop offset="1" stop-color="#0b0d18"/></radialGradient>
  <linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="holo" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#ff0080"/><stop offset=".25" stop-color="#ffcc00"/><stop offset=".5" stop-color="#00ffaa"/><stop offset=".75" stop-color="#00aaff"/><stop offset="1" stop-color="#aa00ff"/></linearGradient>
  <clipPath id="clip"><rect width="300" height="420" rx="22"/></clipPath>
</defs>
<style>
  .pop {{ animation: pop .9s cubic-bezier(.2,1.6,.4,1) both; transform-origin: 150px 140px; }}
  .fade {{ animation: fade .8s .4s both; }}
  .spin {{ animation: spin 14s linear infinite; transform-origin: 150px 140px; }}
  @keyframes pop {{ from {{ transform: scale(0); }} }}
  @keyframes fade {{ from {{ opacity: 0; transform: translateY(10px); }} }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}
</style>
<g clip-path="url(#clip)">
  <rect width="300" height="420" fill="url(#bg)"/>
  {holo}
  <rect x="-200" y="0" width="160" height="420" fill="url(#shine)" transform="skewX(-20)"><animate attributeName="x" values="-260;520" dur="3.2s" repeatCount="indefinite"/></rect>
</g>
<rect x="1.5" y="1.5" width="297" height="417" rx="21" fill="none" stroke="{fg}" stroke-opacity=".75" stroke-width="2"/>
{glow}
<text x="150" y="42" text-anchor="middle" font-family="{font}" font-size="12" font-weight="800" letter-spacing="3" fill="{fg}">{html.escape(TIER_LABEL[lang][tier])}</text>
<circle class="spin" cx="150" cy="140" r="56" fill="none" stroke="{fg}" stroke-opacity=".6" stroke-width="2" stroke-dasharray="6 7"/>
<circle cx="150" cy="140" r="46" fill="{fg}" fill-opacity=".14"/>
<text class="pop" x="150" y="160" text-anchor="middle" font-size="54">{html.escape(a.get("icon") or "🏅")}</text>
<g class="fade" font-family="{font}" text-anchor="middle">
  <text x="150" y="232" font-size="24" font-weight="800" fill="#eef0ff">{title}</text>
  <text x="150" y="260" font-size="13" fill="#a7adc8">{desc}</text>
  {pips}
  <text x="150" y="380" font-size="12" fill="#a7adc8">@{html.escape(login)} · {year}</text>
</g>
</svg>'''


def svg_summary(data: dict, lang: str) -> str:
    s = data["stats"]
    p = data["profile"]
    year = data["meta"]["year"]
    font = "'Inter','Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif"
    labels = {
        "zh": ["總貢獻", "活躍天數", "最長連續", "參與專案", "解鎖成就"],
        "en": ["Contributions", "Active days", "Longest streak", "Projects", "Achievements"],
    }[lang]
    unlocked = sum(1 for a in data["achievements"] if a["unlocked"]) + len((data.get("narrative") or {}).get("custom_achievements", []))
    vals = [s["total_contributions"], s["active_days"], s["longest_streak"], s["repos_contributed"], unlocked]
    cols = ""
    for i, (lab, v) in enumerate(zip(labels, vals)):
        x = 60 + i * 156
        cols += f'''<g style="animation: up .7s {0.15 * i + .3:.2f}s both"><text x="{x}" y="150" font-size="34" font-weight="800" fill="#eef0ff">{v:,}</text>
<text x="{x}" y="176" font-size="13" fill="#a7adc8">{html.escape(lab)}</text></g>'''
    icons = "".join(html.escape(a["icon"]) for a in data["achievements"] if a["unlocked"])[:40]
    title = f"{year} GitHub 年度回顧" if lang == "zh" else f"GitHub {year} in Review"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="840" height="260" viewBox="0 0 840 260">
<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#7c5cff"/><stop offset=".5" stop-color="#22d3ee"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
<linearGradient id="bgg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0e1120"/><stop offset="1" stop-color="#1a1035"/></linearGradient></defs>
<style>@keyframes up {{ from {{ opacity: 0; transform: translateY(14px); }} }} @keyframes slide {{ from {{ stroke-dashoffset: 100; }} }}
@media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; }} }}</style>
<rect width="840" height="260" rx="20" fill="url(#bgg)"/>
<rect x="1" y="1" width="838" height="258" rx="19" fill="none" stroke="url(#g)" stroke-width="2" pathLength="100" stroke-dasharray="100" style="animation: slide 2s ease-out both"/>
<g font-family="{font}">
<text x="60" y="68" font-size="28" font-weight="900" fill="url(#g)" style="animation: up .7s both">{html.escape(title)}</text>
<text x="60" y="96" font-size="14" fill="#a7adc8" style="animation: up .7s .15s both">@{html.escape(p["login"])}</text>
{cols}
<text x="60" y="226" font-size="20" style="animation: up .7s 1.1s both">{icons}</text>
</g></svg>'''


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("analysis")
    ap.add_argument("--narrative", help="narrative.json written by Claude (optional)")
    ap.add_argument("-o", "--output", default="year-review.html")
    ap.add_argument("--cards-dir", help="also write animated SVG achievement cards here")
    ap.add_argument("--lang", choices=["zh", "en"], default=None, help="UI language (default: narrative.lang or zh)")
    args = ap.parse_args()

    with open(args.analysis, encoding="utf-8") as f:
        data = json.load(f)
    narrative = {}
    if args.narrative:
        with open(args.narrative, encoding="utf-8") as f:
            narrative = json.load(f)
    data["narrative"] = narrative
    lang = args.lang or narrative.get("lang") or "zh"

    out = render_html(data, lang)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"[render] wrote {args.output} ({len(out) // 1024} KB)", file=sys.stderr)

    if args.cards_dir:
        os.makedirs(args.cards_dir, exist_ok=True)
        login, year = data["profile"]["login"], data["meta"]["year"]
        cards = [a for a in data["achievements"] if a["unlocked"]]
        cards += [dict(c, unlocked=True, tier=c.get("tier", "epic")) for c in narrative.get("custom_achievements", [])]
        for a in cards:
            path = os.path.join(args.cards_dir, f"{a['id']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(svg_card(a, year, login, lang))
        with open(os.path.join(args.cards_dir, "summary.svg"), "w", encoding="utf-8") as f:
            f.write(svg_summary(data, lang))
        print(f"[render] wrote {len(cards)} achievement cards + summary.svg to {args.cards_dir}/", file=sys.stderr)


if __name__ == "__main__":
    main()
