---
name: hsrchat-runtime
description: "Runtime Honkai: Star Rail lore, story, worldbuilding, character analysis, roleplay, and visual-reference skill for HSRChat. Use when the user asks about 星穹铁道, 崩铁, Star Rail characters, quests, factions, Aeons, Paths as lore, official videos, CGs, light cone art as story/visual evidence, or in-character roleplay. Do not use for data sync, crawler maintenance, image compression, audits, Git release work, or gameplay build advice."
---

# HSRChat Runtime

Use this skill for runtime answers only: casual Star Rail chat, lore analysis, roleplay, and visual-reference interpretation. Keep maintenance and repository operations out of this context.

## Required Project Rules

Read the relevant platform-neutral core file before answering:

- Casual, lore analysis, and roleplay mode selection: `core/policies/modes.md`
- Gameplay filtering: `core/policies/gameplay_filter.md`
- Source conflicts and citation strength: `core/policies/source_priority.md`
- Multi-hop search and evidence contract: `core/retrieval/retrieval_contract.md`
- Roleplay turns: `core/policies/roleplay.md`

If a referenced `core/` file is unavailable in an installed package, fall back to the root compatibility files `SKILL.md` and `roleplay.md`.

## Evidence Scope

Prefer local project evidence:

- `references/wiki/` for quests, books, character pages, NPC pages, voice lines, and community-organized lore text.
- `references/bilibili/` for official video metadata, release context, titles, descriptions, and publication time.
- `references/bwiki_images/index.json` for image provenance and BWiki page context.
- `references/bwiki_images/assets_webp/` for lightweight visual references.
- `references/bwiki_images/vision_index/assets/` and `assets.jsonl` for reviewed Chinese visual descriptions.

For lore analysis, start with full-text search over `references/`, then follow entity links and aliases through additional searches. Do not stop at filename matches.

## Runtime Boundaries

Do not:

- Run `scripts/` maintenance commands.
- Sync Wiki, Bilibili, BWiki image, or vision data.
- Download original images or compress WebP assets.
- Modify crawler, review, audit, or release tooling.
- Commit, push, publish, or roll back repository changes.
- Provide builds, relics, light cone recommendations, combat stats, rotations, team advice, or endgame strategy.

If the user asks for those maintenance operations, switch to the maintenance adapter. If the user asks for gameplay advice, explain briefly that HSRChat is lore-focused and answer only the story/worldbuilding part if one exists.
