import argparse
import os
import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
BWiki_DIR = ROOT_DIR / "references" / "bwiki_images"
INDEX_PATH = BWiki_DIR / "index.json"
OUTPUT_DIR = BWiki_DIR / "assets_webp"
COMPRESSED_INDEX_PATH = BWiki_DIR / "compressed_index.json"
DEFAULT_WORKERS = max(1, os.cpu_count() or 1)


ROLE_CATEGORY = "角色"
CG_CATEGORIES = {"开拓任务", "同行任务", "开拓续闻"}
TEXT_OR_SMALL_CATEGORIES = {"书籍", "冒险任务", "NPC"}


def rel_path(path):
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log(message):
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        safe_message = message.encode("ascii", errors="backslashreplace").decode("ascii")
        print(safe_message, flush=True)


def image_policy(asset):
    appearances = asset.get("appearances") or []
    category = appearances[0].get("wiki_category") if appearances else ""
    name = asset.get("file_name") or ""
    kind = asset.get("asset_kind") or ""

    if category == ROLE_CATEGORY:
        return {
            "quality": 86,
            "max_edge": 1600,
            "reason": "role_painting",
        }

    if category in CG_CATEGORIES and ("CG" in name or "影像" in name or "回想" in name):
        return {
            "quality": 84,
            "max_edge": 1920,
            "reason": "large_story_cg",
        }

    if kind == "dialog_image" or category in TEXT_OR_SMALL_CATEGORIES:
        return {
            "quality": 88,
            "max_edge": None,
            "reason": "text_or_small_context_image",
        }

    return {
        "quality": 86,
        "max_edge": 1920,
        "reason": "default_story_image",
    }


def target_path_for(local_path):
    source_rel = Path(local_path)
    target_rel = source_rel.with_suffix(".webp")
    parts = list(target_rel.parts)
    try:
        assets_index = parts.index("assets")
        parts[assets_index] = "assets_webp"
    except ValueError:
        parts.insert(2, "assets_webp")
    return ROOT_DIR.joinpath(*parts)


def resized_dimensions(width, height, max_edge):
    if not max_edge:
        return width, height
    edge = max(width, height)
    if edge <= max_edge:
        return width, height
    scale = max_edge / edge
    return max(1, round(width * scale)), max(1, round(height * scale))


def load_index():
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def compress_asset(asset, overwrite=False):
    local_path = asset.get("local_path")
    if not local_path:
        return {"status": "skipped", "reason": "missing_local_path"}

    try:
        source_path = ROOT_DIR / local_path
        if not source_path.exists():
            return {"status": "skipped", "reason": "source_missing", "source_path": local_path}

        policy = image_policy(asset)
        target_path = target_path_for(local_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        original_bytes = source_path.stat().st_size
        source_sha256 = sha256_file(source_path)

        with Image.open(source_path) as image:
            original_width, original_height = image.size
            target_width, target_height = resized_dimensions(original_width, original_height, policy["max_edge"])

            if image.mode not in {"RGB", "RGBA"}:
                if "A" in image.getbands() or "transparency" in image.info:
                    image = image.convert("RGBA")
                else:
                    image = image.convert("RGB")

            if (target_width, target_height) != image.size:
                image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

            target_is_valid = target_path.exists() and target_path.stat().st_size > 0
            if overwrite or not target_is_valid:
                temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
                if temp_path.exists():
                    temp_path.unlink()
                image.save(
                    temp_path,
                    "WEBP",
                    quality=policy["quality"],
                    method=4,
                    exact=True,
                )
                temp_path.replace(target_path)

        compressed_bytes = target_path.stat().st_size
        ratio = compressed_bytes / original_bytes if original_bytes else 0

        return {
            "status": "compressed",
            "source_path": local_path,
            "compressed_path": rel_path(target_path),
            "file_name": asset.get("file_name"),
            "asset_kind": asset.get("asset_kind"),
            "wiki_category": (asset.get("appearances") or [{}])[0].get("wiki_category"),
            "policy": policy,
            "original": {
                "bytes": original_bytes,
                "width": original_width,
                "height": original_height,
                "sha256": source_sha256,
            },
            "compressed": {
                "bytes": compressed_bytes,
                "width": target_width,
                "height": target_height,
                "sha256": sha256_file(target_path),
            },
            "saved_bytes": original_bytes - compressed_bytes,
            "compressed_ratio": round(ratio, 4),
            "saved_percent": round((1 - ratio) * 100, 2),
        }
    except Exception as exc:
        return {
            "status": "compress_failed",
            "reason": str(exc),
            "source_path": local_path,
            "file_name": asset.get("file_name"),
            "asset_kind": asset.get("asset_kind"),
            "wiki_category": (asset.get("appearances") or [{}])[0].get("wiki_category"),
        }


def summarize(results):
    compressed = [result for result in results if result.get("status") == "compressed"]
    skipped = [result for result in results if result.get("status") != "compressed"]
    original_total = sum(result["original"]["bytes"] for result in compressed)
    compressed_total = sum(result["compressed"]["bytes"] for result in compressed)
    saved_total = original_total - compressed_total
    by_category = {}
    for result in compressed:
        category = result.get("wiki_category") or "_unknown"
        bucket = by_category.setdefault(
            category,
            {"count": 0, "original_bytes": 0, "compressed_bytes": 0, "saved_bytes": 0},
        )
        bucket["count"] += 1
        bucket["original_bytes"] += result["original"]["bytes"]
        bucket["compressed_bytes"] += result["compressed"]["bytes"]
        bucket["saved_bytes"] += result["saved_bytes"]

    for bucket in by_category.values():
        original = bucket["original_bytes"]
        compressed_bytes = bucket["compressed_bytes"]
        bucket["original_mib"] = round(original / (1024**2), 2)
        bucket["compressed_mib"] = round(compressed_bytes / (1024**2), 2)
        bucket["saved_mib"] = round(bucket["saved_bytes"] / (1024**2), 2)
        bucket["saved_percent"] = round((1 - compressed_bytes / original) * 100, 2) if original else 0

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_index": rel_path(INDEX_PATH),
        "output_dir": rel_path(OUTPUT_DIR),
        "compressed_count": len(compressed),
        "skipped_count": len(skipped),
        "original_bytes": original_total,
        "compressed_bytes": compressed_total,
        "saved_bytes": saved_total,
        "original_mib": round(original_total / (1024**2), 2),
        "compressed_mib": round(compressed_total / (1024**2), 2),
        "saved_mib": round(saved_total / (1024**2), 2),
        "saved_percent": round((1 - compressed_total / original_total) * 100, 2) if original_total else 0,
        "by_category": dict(sorted(by_category.items())),
    }


def main():
    parser = argparse.ArgumentParser(description="Create WebP copies of downloaded BWiki images.")
    parser.add_argument("--overwrite", action="store_true", help="rewrite existing compressed WebP files")
    parser.add_argument("--limit", type=int, default=None, help="compress only the first N indexed local assets")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="parallel compression workers")
    args = parser.parse_args()

    index = load_index()
    assets = [asset for asset in index.get("assets", []) if asset.get("local_path")]
    if args.limit is not None:
        assets = assets[: args.limit]

    results = []
    total = len(assets)
    worker_count = max(1, args.workers)
    if worker_count == 1:
        for offset, asset in enumerate(assets, start=1):
            result = compress_asset(asset, overwrite=args.overwrite)
            results.append(result)
            if offset == 1 or offset % 10 == 0 or offset == total:
                log(f"[compress] {offset}/{total} {result.get('status')} {result.get('source_path') or result.get('reason')}")
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(compress_asset, asset, args.overwrite) for asset in assets]
            for offset, future in enumerate(as_completed(futures), start=1):
                result = future.result()
                results.append(result)
                if offset == 1 or offset % 10 == 0 or offset == total:
                    log(f"[compress] {offset}/{total} {result.get('status')} {result.get('source_path') or result.get('reason')}")

    report = {
        "summary": summarize(results),
        "assets": results,
    }
    COMPRESSED_INDEX_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(
        "[done] "
        f"{report['summary']['compressed_count']} files, "
        f"{report['summary']['original_mib']} MiB -> {report['summary']['compressed_mib']} MiB "
        f"saved {report['summary']['saved_mib']} MiB"
    )
    log(f"[index] {rel_path(COMPRESSED_INDEX_PATH)}")


if __name__ == "__main__":
    main()
