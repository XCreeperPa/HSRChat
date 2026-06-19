# Retrieval Contract

This contract describes how any HSRChat adapter should retrieve evidence.

## Inputs

A runtime request may include:

- User question or roleplay turn.
- Mode: casual, lore analysis, or roleplay.
- Entity hints: characters, factions, places, Aeons, Paths, missions, books, videos, images.
- Spoiler boundary, if provided by the user.

## Search Scope

Default local evidence lives in:

- `references/wiki/`
- `references/bilibili/`
- `references/bwiki_images/index.json`
- `references/bwiki_images/assets_webp/`
- `references/bwiki_images/vision_index/assets/`
- `references/bwiki_images/vision_index/assets.jsonl`

Do not search outside the project for local evidence unless the user explicitly asks for external verification.

## Search Method

For lore analysis and roleplay grounding:

1. Start with full-text search over content, not only filenames.
2. Read the strongest direct hits.
3. Extract aliases, hidden names, locations, organizations, events, and repeated concepts.
4. Search those extracted entities again.
5. Compare source types using `core/policies/source_priority.md`.
6. Filter gameplay content using `core/policies/gameplay_filter.md`.

## Outputs

Return or internally use evidence with:

- Source path or media identifier.
- Source type.
- Relevant excerpt or summarized fact.
- Confidence and conflict notes when needed.
- Gameplay-contamination flag when the retrieved text includes mechanics.

Roleplay outputs must use evidence internally and hide retrieval details from the character voice.
