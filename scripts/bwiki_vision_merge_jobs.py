#!/usr/bin/env python3
"""Merge and validate BWiki image vision JSONL worker outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "references" / "bwiki_images" / "vision_jobs"


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"missing file: {rel(path)}"]
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel(path)}:{line_no}: invalid JSON: {exc}")
                continue
            if not isinstance(value, dict):
                errors.append(f"{rel(path)}:{line_no}: line is not an object")
                continue
            records.append(value)
    return records, errors


def load_expected(manifest: Path) -> list[str]:
    records, errors = read_jsonl(manifest)
    if errors:
        raise SystemExit("\n".join(errors))
    paths = []
    for record in records:
        image_path = record.get("图片路径")
        if not isinstance(image_path, str) or not image_path:
            raise SystemExit(f"manifest record missing 图片路径: {record}")
        paths.append(image_path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(JOBS_DIR / "trial_manifest.jsonl"))
    parser.add_argument("--outputs-dir", default=str(JOBS_DIR / "outputs"))
    parser.add_argument("--pattern", default="result_*.jsonl")
    parser.add_argument("--merged", default=str(JOBS_DIR / "trial_merged_assets.jsonl"))
    parser.add_argument("--report", default=str(JOBS_DIR / "trial_validation_report.json"))
    args = parser.parse_args()

    manifest = Path(args.manifest)
    outputs_dir = Path(args.outputs_dir)
    expected = load_expected(manifest)
    expected_set = set(expected)

    records: list[dict] = []
    errors: list[str] = []
    for output in sorted(outputs_dir.glob(args.pattern), key=lambda p: p.name):
        chunk, chunk_errors = read_jsonl(output)
        records.extend(chunk)
        errors.extend(chunk_errors)

    by_path: dict[str, list[dict]] = {}
    for record in records:
        image_path = record.get("图片路径")
        if not isinstance(image_path, str) or not image_path:
            errors.append(f"record missing 图片路径: {record}")
            continue
        by_path.setdefault(image_path, []).append(record)
        if image_path not in expected_set:
            errors.append(f"unexpected 图片路径: {image_path}")

    missing = [path for path in expected if path not in by_path]
    duplicates = {path: len(items) for path, items in by_path.items() if len(items) > 1}
    errors.extend(f"missing 图片路径: {path}" for path in missing)
    errors.extend(f"duplicate 图片路径: {path} x{count}" for path, count in duplicates.items())

    merged_records = []
    for image_path in expected:
        items = by_path.get(image_path)
        if items:
            merged_records.append(items[0])

    merged = Path(args.merged)
    merged.parent.mkdir(parents=True, exist_ok=True)
    with merged.open("w", encoding="utf-8", newline="\n") as handle:
        for record in merged_records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    report = {
        "expected": len(expected),
        "merged": len(merged_records),
        "outputs": [rel(path) for path in sorted(outputs_dir.glob(args.pattern), key=lambda p: p.name)],
        "missing": missing,
        "duplicates": duplicates,
        "errors": errors,
        "ok": not errors and len(merged_records) == len(expected),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
