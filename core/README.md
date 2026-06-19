# HSRChat Core

`core/` contains platform-neutral HSRChat rules and contracts. It should be usable by Codex, Claude Project instructions, OpenAI Agents SDK tools, Cursor, generic Markdown packages, or future RAG services.

Do not put platform-specific Skill, plugin, MCP, install, or Git workflow instructions here. Those belong in `adapters/` or maintenance docs.

## Contents

- `policies/`: runtime modes, gameplay filtering, source priority, and roleplay behavior.
- `retrieval/`: how adapters should search local evidence and represent retrieved support.
- `schemas/`: JSON schema drafts for future runtime data under `data/runtime/` or `dist/`.

## Current Status

This is the first-stage architecture skeleton. Existing raw data remains in `references/`, and existing scripts remain in `scripts/` until a later migration moves maintenance tooling under `maintenance/`.
