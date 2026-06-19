#!/usr/bin/env python3
"""Split the reviewed BWiki vision JSONL into image-mirrored JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_WEBP = ROOT / "references" / "bwiki_images" / "assets_webp"
VISION_INDEX = ROOT / "references" / "bwiki_images" / "vision_index"
DEFAULT_JSONL = VISION_INDEX / "assets.jsonl"
DEFAULT_ASSETS_DIR = VISION_INDEX / "assets"


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def image_path_from_record(record: dict) -> str:
    value = record.get("图片路径")
    return value.replace("\\", "/") if isinstance(value, str) else ""


def description_path_for_image(image_path: str, assets_dir: Path) -> Path:
    image = (ROOT / image_path).resolve()
    relative = image.relative_to(ASSETS_WEBP.resolve())
    return assets_dir / relative.with_suffix(".json")


def load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{rel(path)}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise SystemExit(f"{rel(path)}:{line_no}: line is not an object")
        records.append(value)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", default=str(DEFAULT_JSONL), help="Source reviewed JSONL.")
    parser.add_argument("--assets-dir", default=str(DEFAULT_ASSETS_DIR), help="Output mirrored JSON directory.")
    parser.add_argument("--clean", action="store_true", help="Remove old JSON files under assets-dir before writing.")
    args = parser.parse_args()

    jsonl = Path(args.jsonl)
    assets_dir = Path(args.assets_dir)
    records = load_jsonl(jsonl)

    if args.clean and assets_dir.exists():
        for old in assets_dir.rglob("*.json"):
            old.unlink()

    seen: set[str] = set()
    written: list[str] = []
    for record in records:
        image_path = image_path_from_record(record)
        if not image_path:
            raise SystemExit(f"record missing 图片路径: {record}")
        if image_path in seen:
            raise SystemExit(f"duplicate 图片路径: {image_path}")
        seen.add(image_path)
        image_file = ROOT / image_path
        if not image_file.exists():
            raise SystemExit(f"image file not found: {image_path}")
        out = description_path_for_image(image_path, assets_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(rel(out))

    print(json.dumps({"source": rel(jsonl), "assets_dir": rel(assets_dir), "written": len(written)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
