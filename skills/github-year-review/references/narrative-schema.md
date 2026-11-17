# narrative.json schema

Every field is optional. Text fields may be a plain string, or `{"zh": "...", "en": "..."}`
for bilingual output.

```jsonc
{
  "lang": "zh",                         // "zh" | "en" – UI language if --lang is not passed
  "headline": "…",                      // one sentence, typed out in the hero
  "theme_words": ["AI Agents", "Rust"], // 3–6 chips under the headline
  "project_order": ["owner/repo", …],   // curated order; unlisted projects follow
  "max_projects": 8,                    // default 12
  "projects": {
    "owner/repo": {                     // key = projects[].id from analysis.json
      "category": "AI 系統",
      "tagline": "One-line pitch",
      "highlights": ["Concrete thing built", "…"]   // 1–3 items
    }
  },
  "achievements": {                     // flavor text on the back of built-in cards
    "night_owl": "…"
  },
  "custom_achievements": [
    {
      "id": "first_launch",             // file-name safe, unique
      "icon": "🚀",                     // one emoji
      "tier": "epic",                   // common | rare | epic | legendary
      "title": "首次上線",
      "desc": "Short line on the card front",
      "detail": "Longer story on the card back"
    }
  ],
  "summary": "2–4 sentences recapping the year",
  "closing": "1–2 sentences looking forward"
}
```

## Tier guidance for custom achievements
- **common** – a nice milestone (first Docker setup, first CI pipeline)
- **rare** – meaningful (shipped a v1.0, first external contributor)
- **epic** – impressive (built a non-trivial system from scratch, 100+ stars)
- **legendary** – exceptional (widely adopted project, merged into a major OSS project)

Use legendary sparingly — it triggers extra confetti and a glowing border.
