# HSRChat Agent Guidance

HSRChat is moving from a single Codex Skill into an agent-agnostic Star Rail domain knowledge system. Keep runtime use and maintenance work separate.

## Runtime Work

Use runtime guidance for:

- Honkai: Star Rail lore, story, worldbuilding, character analysis, roleplay, and visual-reference answers.
- Casual chat, lore analysis, and roleplay mode selection.
- Reading `references/wiki/`, `references/bilibili/`, and `references/bwiki_images/` as evidence.

Do not run sync, download, compression, review, audit, Git release, or publishing scripts during ordinary runtime Q&A.

## Maintenance Work

Use maintenance guidance only when the user asks to:

- Sync Wiki, Bilibili, BWiki image, or vision-description data.
- Modify crawler, compression, review, audit, or release scripts.
- Audit data quality, sensitive files, original-image cache boundaries, or generated indexes.
- Commit, push, publish, or roll back HSRChat data or tooling changes.

Before maintenance work, read `references/docs/devops.md` and `references/docs/data_sources.md`.

## Version-Control Boundaries

- Never commit `config_secrets.json`.
- Never commit `references/bwiki_images/assets/`.
- Commit WebP reference images only from `references/bwiki_images/assets_webp/`.
- Treat raw Wiki data as archival evidence; filter gameplay contamination through runtime policy or derived indexes, not destructive raw cleanup.
