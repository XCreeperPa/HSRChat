---
name: hsrchat-maintenance
description: "Maintenance skill for the HSRChat repository and data pipeline. Use when the user asks to sync or repair Wiki, Bilibili, BWiki image, WebP, or vision-description data; modify crawler, compression, review, audit, schema, or release tooling; check sensitive-file boundaries; inspect data quality; commit, push, publish, or roll back HSRChat changes. Do not use for ordinary Star Rail lore Q&A or roleplay."
---

# HSRChat Maintenance

Use this skill only for repository, data, and tooling maintenance. Keep ordinary lore answers and roleplay in the runtime skill.

## Required Reading

Before maintenance work, read:

- `AGENTS.md` for project-level runtime/maintenance separation.
- `references/docs/devops.md` for safety, Git, and data-contamination rules.
- `references/docs/data_sources.md` for source-specific sync workflows.
- `references/docs/maintenance.md` when changing or running scripts.
- `references/docs/next_stage_architecture_plan.md` when changing architecture, adapters, core rules, or directory layout.

Read source-specific docs as needed:

- Wiki text: `references/docs/source_wiki.md`
- Bilibili metadata: `references/docs/source_bilibili.md`
- BWiki images and vision index: `references/docs/source_bwiki_images.md`

## Maintenance Workflow

1. Check `git status` before changing data or running sync scripts.
2. Verify `config_secrets.json` and `references/bwiki_images/assets/` are ignored and not staged.
3. Run the smallest relevant command first, using test or estimate mode where available.
4. Inspect `git status` and `git diff` after generation or sync.
5. Audit generated indexes before committing, especially image counts, JSON/JSONL parseability, duplicate paths, and empty descriptions.
6. Commit only after the data and version-control boundaries are verified.

## Script Boundaries

Current compatibility script paths remain under `scripts/`:

- `scripts/wiki/`
- `scripts/bilibili/`
- `scripts/bwiki_images/`
- `scripts/vision/`

The target architecture will eventually move maintenance tooling under `maintenance/scripts/`. Until paths are migrated and docs are updated together, keep existing commands working.

## Runtime Boundary

Do not answer ordinary lore or roleplay requests from this skill. If the user asks about Star Rail story, characters, factions, official videos, CGs, or roleplay without asking to change data or tooling, use the runtime skill instead.
