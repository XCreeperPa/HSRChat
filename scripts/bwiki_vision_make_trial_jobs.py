#!/usr/bin/env python3
"""Create small per-category trial shards for BWiki image vision annotation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_WEBP = ROOT / "references" / "bwiki_images" / "assets_webp"
JOBS_DIR = ROOT / "references" / "bwiki_images" / "vision_jobs"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def build_records(limit_per_category: int) -> list[dict]:
    records: list[dict] = []
    for category_dir in sorted(ASSETS_WEBP.iterdir(), key=lambda p: p.name):
        if not category_dir.is_dir():
            continue
        images = sorted(category_dir.glob("*.webp"), key=lambda p: p.name)
        for image in images[:limit_per_category]:
            records.append(
                {
                    "图片路径": rel(image),
                    "图片类别": category_dir.name,
                    "图片标题": image.stem,
                }
            )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-per-category", type=int, default=10)
    parser.add_argument("--shard-size", type=int, default=13)
    parser.add_argument("--prefix", default="trial")
    args = parser.parse_args()

    records = build_records(args.limit_per_category)
    manifest = JOBS_DIR / f"{args.prefix}_manifest.jsonl"
    write_jsonl(manifest, records)

    shard_dir = JOBS_DIR / "shards"
    for old in shard_dir.glob(f"{args.prefix}_*.jsonl"):
        old.unlink()

    shards = []
    for index in range(0, len(records), args.shard_size):
        shard_index = index // args.shard_size
        shard_records = records[index : index + args.shard_size]
        shard_path = shard_dir / f"{args.prefix}_{shard_index:03d}.jsonl"
        write_jsonl(shard_path, shard_records)
        shards.append(shard_path)

    counts: dict[str, int] = {}
    for record in records:
        counts[record["图片类别"]] = counts.get(record["图片类别"], 0) + 1

    summary = {
        "manifest": rel(manifest),
        "total": len(records),
        "limit_per_category": args.limit_per_category,
        "shard_size": args.shard_size,
        "shards": [rel(path) for path in shards],
        "counts": dict(sorted(counts.items())),
    }
    summary_path = JOBS_DIR / f"{args.prefix}_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
