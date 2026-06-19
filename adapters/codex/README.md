# HSRChat Codex Adapter

This adapter validates the runtime/maintenance split inside Codex without breaking the existing root `SKILL.md` installation.

## Skills

- `skills/hsrchat-runtime/`: Star Rail lore, story analysis, roleplay, and visual-reference answers.
- `skills/hsrchat-maintenance/`: data sync, crawler and image pipeline work, vision index review, audits, commits, pushes, and releases.

The root `SKILL.md` remains a compatibility entry during migration. Future packaging can generate Codex release artifacts from this adapter into `dist/codex/`.
