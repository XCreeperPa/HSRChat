import argparse
import os
import hashlib
import html
import sys
import json
import mimetypes
import re
import socket
import struct
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT_DIR / "references" / "wiki"
ROLE_DIR = WIKI_DIR / "角色"
OUTPUT_DIR = ROOT_DIR / "references" / "bwiki_images"
ASSETS_DIR = OUTPUT_DIR / "assets"
INDEX_PATH = OUTPUT_DIR / "index.json"
REPORT_PATH = OUTPUT_DIR / "estimate_report.json"
API_URL = "https://wiki.biligame.com/sr/api.php"
DEFAULT_LIMIT_BYTES = 1024 * 1024 * 1024
DEFAULT_WORKERS = max(4, min(32, (os.cpu_count() or 4) * 4))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://wiki.biligame.com/sr/%E9%A6%96%E9%A1%B5",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

PATTERNS = [
    ("picture_zoom", re.compile(r"\{\{图片放大\|([^|}\n]+)")),
    ("dialog_image", re.compile(r"\{\{角色对话\|[^\n{}]*?\|图片\|([^|}\n]+)")),
    ("filepath_template", re.compile(r"\{\{filepath:([^}\n]+)\}\}")),
    ("special_file_path", re.compile(r"特殊:文件路径/([^\"')\s]+)")),
    ("direct_url", re.compile(r"https://patchwiki\.biligame\.com/images/sr/[^\s\"')<>]+")),
    ("file_link", re.compile(r"\[\[(?:File|file|文件):([^|\]\n]+)")),
]

HIGH_VALUE_KINDS = {"picture_zoom", "dialog_image", "file_link", "character_painting"}
socket.setdefaulttimeout(20)


def log(message):
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        safe_message = message.encode("ascii", errors="backslashreplace").decode("ascii")
        print(safe_message, flush=True)


def clean_filename(name):
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    cleaned = re.sub(r"[\x00-\x1f]", "_", cleaned)
    return cleaned or "unnamed"


def normalize_file_ref(value):
    value = html.unescape(urllib.parse.unquote(value)).strip()
    value = re.sub(r"^(?:File|file|文件):", "", value).strip()
    return value


def rel_path(path):
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def line_px_sizes(line):
    return [int(size) for size in re.findall(r"\|(\d{1,4})px(?:\||\])", line, flags=re.I)]


def classify_candidate(kind, line, file_name):
    lower_name = file_name.lower()
    sizes = line_px_sizes(line)

    if kind in {"special_file_path", "direct_url", "filepath_template"}:
        return "discard", "decorative_or_unscoped_reference"

    if "{{图标|" in line:
        return "discard", "icon_template"

    if kind == "file_link" and sizes and max(sizes) <= 64:
        return "discard", "small_file_icon"

    if re.search(r"(虚数|量子|火|冰|雷|风|物理)\.(png|jpg|jpeg|webp)$", lower_name):
        return "discard", "combat_or_element_icon"

    if kind in HIGH_VALUE_KINDS:
        return "high", None

    return "discard", "unsupported_reference_kind"


def make_candidate(kind, match, path, lines, line_index):
    line = lines[line_index]
    original_ref = match.group(0)

    if kind == "direct_url":
        parsed = urllib.parse.urlparse(original_ref)
        file_name = Path(urllib.parse.unquote(parsed.path)).name
        resolved_url = original_ref
    else:
        file_name = normalize_file_ref(match.group(1))
        resolved_url = None

    priority, excluded_reason = classify_candidate(kind, line, file_name)
    wiki_rel = path.relative_to(WIKI_DIR)
    parts = wiki_rel.parts
    context_before = lines[line_index - 1].strip() if line_index > 0 else ""
    context_after = lines[line_index + 1].strip() if line_index + 1 < len(lines) else ""
    identity = f"{kind}\n{file_name}\n{resolved_url or ''}"

    return {
        "id": hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
        "source": "bwiki_image",
        "asset_kind": kind,
        "priority": priority,
        "excluded_reason": excluded_reason,
        "file_name": file_name,
        "original_ref": original_ref,
        "resolved_url": resolved_url,
        "wiki_category": parts[0] if len(parts) > 1 else "",
        "wiki_page_title": path.stem,
        "wiki_text_path": rel_path(path),
        "line": line_index + 1,
        "context_before": context_before,
        "context_line": line.strip(),
        "context_after": context_after,
    }


def collect_references():
    references = []
    for path in sorted(WIKI_DIR.rglob("*.txt")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_index, line in enumerate(lines):
            for kind, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    references.append(make_candidate(kind, match, path, lines, line_index))
    return references


def extract_role_name(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\|名称=([^\n|<]+)", text)
    if match:
        return match.group(1).strip()
    return path.stem


def collect_character_paintings():
    references = []
    if not ROLE_DIR.exists():
        return references

    for path in sorted(ROLE_DIR.glob("*.txt")):
        page_title = path.stem
        role_name = extract_role_name(path)
        base_names = [role_name]

        if role_name.startswith("开拓者•"):
            path_name = role_name.split("•", 1)[1]
            base_names.extend([f"开拓者星•{path_name}", f"开拓者穹•{path_name}"])

        for base_name in dict.fromkeys(base_names):
            for suffix, label in [
                ("立绘.png", "角色立绘"),
            ]:
                file_name = f"{base_name}{suffix}"
                identity = f"character_painting\n{file_name}\n{page_title}"
                display_name = base_name
                if base_name.startswith("开拓者星•"):
                    display_name = f"{role_name}（星）"
                elif base_name.startswith("开拓者穹•"):
                    display_name = f"{role_name}（穹）"

                references.append(
                    {
                        "id": hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
                        "source": "bwiki_image",
                        "asset_kind": "character_painting",
                        "priority": "high",
                        "excluded_reason": None,
                        "file_name": file_name,
                        "original_ref": f"File:{file_name}",
                        "resolved_url": None,
                        "wiki_category": "角色",
                        "wiki_page_title": page_title,
                        "wiki_text_path": rel_path(path),
                        "line": None,
                        "context_before": f"角色名: {display_name}",
                        "context_line": f"渲染角色页图片: {label}",
                        "context_after": "",
                        "rendered_page_url": "https://wiki.biligame.com/sr/" + urllib.parse.quote(page_title),
                        "character_image_label": label,
                        "html_class": None,
                    }
                )

    return references


def dedupe_high_value(references):
    assets = {}
    discarded = []

    for ref in references:
        if ref["priority"] != "high":
            discarded.append(ref)
            continue

        key = ref["resolved_url"] or ref["file_name"]
        asset = assets.get(key)
        appearance = {
            "wiki_category": ref["wiki_category"],
            "wiki_page_title": ref["wiki_page_title"],
            "wiki_text_path": ref["wiki_text_path"],
            "line": ref["line"],
            "original_ref": ref["original_ref"],
            "context_before": ref["context_before"],
            "context_line": ref["context_line"],
            "context_after": ref["context_after"],
            "asset_kind": ref["asset_kind"],
            "rendered_page_url": ref.get("rendered_page_url"),
            "character_image_label": ref.get("character_image_label"),
            "html_class": ref.get("html_class"),
        }

        if asset:
            asset["appearances"].append(appearance)
            continue

        asset_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        assets[key] = {
            "id": asset_id,
            "source": "bwiki_image",
            "priority": "high",
            "file_name": ref["file_name"],
            "resolved_url": ref["resolved_url"],
            "direct_reference": ref["resolved_url"] is not None,
            "asset_kind": ref["asset_kind"],
            "appearances": [appearance],
            "mime": None,
            "width": None,
            "height": None,
            "bytes": None,
            "sha1": None,
            "sha256": None,
            "bwiki_file_title": None,
            "bwiki_file_timestamp": None,
            "local_path": None,
            "status": "pending",
            "error": None,
        }

    return list(assets.values()), discarded


def request_json(params, retries=3):
    query = urllib.parse.urlencode(params)
    url = f"{API_URL}?{query}"
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"API request failed: {exc}") from exc
            time.sleep((attempt + 1) * 2.0)
    return None


def resolve_batch(file_names):
    if not file_names:
        return {}

    data = request_json(
        {
            "action": "query",
            "titles": "|".join(f"File:{name}" for name in file_names),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|sha1|timestamp",
            "format": "json",
            "utf8": "1",
        }
    )
    resolved = {}
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        title = page.get("title") or ""
        file_name = re.sub(r"^(?:File|文件):", "", title)
        imageinfo = page.get("imageinfo") or []
        if imageinfo:
            info = dict(imageinfo[0])
            info["pageid"] = page.get("pageid")
            info["title"] = title
            resolved[file_name] = info
    return resolved


def estimate_batch(batch):
    names = [asset["file_name"] for asset in batch]
    try:
        resolved = resolve_batch(names)
    except Exception as exc:
        for asset in batch:
            asset["status"] = "estimate_failed"
            asset["error"] = str(exc)
        return batch

    for asset in batch:
        info = resolved.get(asset["file_name"])
        if not info:
            asset["status"] = "estimate_failed"
            asset["error"] = "No imageinfo found"
            continue
        apply_image_info(asset, info)
        asset["status"] = "estimated"

    return batch


def estimate_assets(assets, sleep_seconds=0.0, workers=DEFAULT_WORKERS):
    named_assets = [asset for asset in assets if not asset["resolved_url"]]
    batches = [named_assets[index : index + 50] for index in range(0, len(named_assets), 50)]
    if not batches:
        return

    worker_count = max(1, workers)
    if worker_count == 1:
        for offset, batch in enumerate(batches, start=1):
            estimate_batch(batch)
            log(f"[estimate] batch {offset}/{len(batches)}")
            if sleep_seconds:
                time.sleep(sleep_seconds)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(estimate_batch, batch) for batch in batches]
            for offset, future in enumerate(as_completed(futures), start=1):
                future.result()
                log(f"[estimate] batch {offset}/{len(batches)}")
                if sleep_seconds:
                    time.sleep(sleep_seconds)

    direct_assets = [asset for asset in assets if asset["direct_reference"] and asset["status"] == "pending"]
    for asset in direct_assets:
        asset["status"] = "estimated_url_only"


def dedupe_assets_by_sha1(assets):
    deduped = []
    by_sha1 = {}

    for asset in assets:
        sha1 = asset.get("sha1")
        if not sha1:
            deduped.append(asset)
            continue

        existing = by_sha1.get(sha1)
        if not existing:
            by_sha1[sha1] = asset
            deduped.append(asset)
            continue

        existing["appearances"].extend(asset.get("appearances", []))
        existing.setdefault("duplicate_file_names", []).append(asset["file_name"])

    return deduped


def apply_image_info(asset, info):
    asset["resolved_url"] = info.get("url")
    asset["mime"] = info.get("mime")
    asset["width"] = info.get("width")
    asset["height"] = info.get("height")
    asset["bytes"] = info.get("size")
    asset["sha1"] = info.get("sha1")
    asset["bwiki_file_title"] = info.get("title")
    asset["bwiki_file_timestamp"] = info.get("timestamp")


def download_bytes(url, max_bytes, retries=3):
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=35) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > max_bytes:
                    raise RuntimeError(f"remote file is larger than max_bytes: {length}")

                chunks = []
                total = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise RuntimeError(f"download exceeded max_bytes: {total}")
                    chunks.append(chunk)
                return b"".join(chunks), dict(response.headers), response.geturl()
        except Exception as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"download failed: {exc}") from exc
            time.sleep((attempt + 1) * 2.0)
    return b"", {}, url


def is_image_bytes(data):
    return (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        or data.startswith(b"\xff\xd8")
        or data.startswith(b"GIF87a")
        or data.startswith(b"GIF89a")
        or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")
    )


def infer_dimensions(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])

    if data.startswith(b"\xff\xd8"):
        offset = 2
        sof_markers = {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }
        while offset + 9 < len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in (0xD8, 0xD9):
                continue
            if offset + 2 > len(data):
                break
            block_len = int.from_bytes(data[offset : offset + 2], "big")
            if marker in sof_markers and offset + 7 < len(data):
                height = int.from_bytes(data[offset + 3 : offset + 5], "big")
                width = int.from_bytes(data[offset + 5 : offset + 7], "big")
                return width, height
            offset += block_len

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and data[12:16] == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height

    return None, None


def ensure_extension(file_name, mime):
    if Path(file_name).suffix:
        return file_name
    guessed = mimetypes.guess_extension(mime or "")
    return f"{file_name}{guessed or '.img'}"


def download_asset(asset, max_single_bytes):
    if asset["status"] not in {"estimated", "estimated_url_only"} or not asset["resolved_url"]:
        return asset

    try:
        mime = asset["mime"]
        category = clean_filename(asset["appearances"][0]["wiki_category"] or "_uncategorized")
        output_name = ensure_extension(clean_filename(asset["file_name"]), mime)
        output_path = ASSETS_DIR / category / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and output_path.stat().st_size > 0:
            data = output_path.read_bytes()
            if not is_image_bytes(data):
                raise RuntimeError("existing file did not look like an image")
            asset.update(
                {
                    "status": "downloaded",
                    "local_path": rel_path(output_path),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "error": None,
                }
            )
            return asset

        data, headers, final_url = download_bytes(asset["resolved_url"], max_single_bytes)
        if not data or not is_image_bytes(data):
            raise RuntimeError("response did not look like an image")

        mime = mime or headers.get("Content-Type", "").split(";")[0]
        width = asset["width"]
        height = asset["height"]
        if not width or not height:
            width, height = infer_dimensions(data)

        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        if temp_path.exists():
            temp_path.unlink()
        temp_path.write_bytes(data)
        temp_path.replace(output_path)

        asset.update(
            {
                "status": "downloaded",
                "resolved_url": final_url,
                "local_path": rel_path(output_path),
                "mime": mime,
                "width": width,
                "height": height,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "error": None,
            }
        )
    except Exception as exc:
        asset["status"] = "download_failed"
        asset["error"] = str(exc)

    return asset


def download_assets(assets, max_single_bytes, sleep_seconds=0.0, workers=DEFAULT_WORKERS):
    targets = [
        asset
        for asset in assets
        if asset["status"] in {"estimated", "estimated_url_only"} and asset["resolved_url"]
    ]
    if not targets:
        return

    worker_count = max(1, workers)
    if worker_count == 1:
        for offset, asset in enumerate(targets, start=1):
            download_asset(asset, max_single_bytes)
            log(f"[download] {offset}/{len(targets)} {asset.get('status')} {asset.get('local_path') or asset.get('file_name')}")
            if sleep_seconds:
                time.sleep(sleep_seconds)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(download_asset, asset, max_single_bytes) for asset in targets]
            for offset, future in enumerate(as_completed(futures), start=1):
                asset = future.result()
                log(f"[download] {offset}/{len(targets)} {asset.get('status')} {asset.get('local_path') or asset.get('file_name')}")
                if sleep_seconds:
                    time.sleep(sleep_seconds)


def summarize(assets, discarded, all_references, limit_bytes):
    known_assets = [asset for asset in assets if isinstance(asset.get("bytes"), int)]
    known_total = sum(asset["bytes"] for asset in known_assets)
    unknown_count = len([asset for asset in assets if not isinstance(asset.get("bytes"), int)])
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "limit_bytes": limit_bytes,
        "limit_gib": round(limit_bytes / (1024**3), 4),
        "total_references_seen": len(all_references),
        "discarded_reference_count": len(discarded),
        "high_value_unique_count": len(assets),
        "known_size_count": len(known_assets),
        "unknown_size_count": unknown_count,
        "estimated_total_bytes": known_total,
        "estimated_total_mib": round(known_total / (1024**2), 2),
        "estimated_total_gib": round(known_total / (1024**3), 4),
        "over_limit": known_total > limit_bytes,
        "status_counts": status_counts(assets),
        "discarded_reason_counts": discarded_reason_counts(discarded),
    }


def status_counts(assets):
    counts = {}
    for asset in assets:
        status = asset.get("status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def discarded_reason_counts(discarded):
    counts = {}
    for ref in discarded:
        reason = ref.get("excluded_reason") or "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Estimate or download high-value BWiki image references.")
    parser.add_argument("--download", action="store_true", help="download assets after estimating size")
    parser.add_argument("--limit-bytes", type=int, default=DEFAULT_LIMIT_BYTES, help="abort download above this size")
    parser.add_argument("--max-single-bytes", type=int, default=64 * 1024 * 1024, help="max bytes for one image")
    parser.add_argument("--sleep", type=float, default=0.0, help="delay between completed network tasks")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="parallel workers for estimate/download")
    args = parser.parse_args()

    log("[scan] collecting image references from local Wikitext...")
    references = collect_references()
    log("[scan] collecting character paintings from rendered role pages...")
    references.extend(collect_character_paintings())
    assets, discarded = dedupe_high_value(references)
    log(f"[scan] references={len(references)}, high_value_unique={len(assets)}, discarded={len(discarded)}")

    log("[estimate] resolving remote image sizes without downloading assets...")
    estimate_assets(assets, sleep_seconds=args.sleep, workers=args.workers)
    assets = dedupe_assets_by_sha1(assets)
    summary = summarize(assets, discarded, references, args.limit_bytes)

    report = {
        "summary": summary,
        "assets": assets,
        "discarded_references": discarded,
    }
    write_json(REPORT_PATH, report)
    log(
        "[estimate] high-value known total: "
        f"{summary['estimated_total_mib']} MiB across {summary['known_size_count']} assets "
        f"({summary['unknown_size_count']} unknown)"
    )
    log(f"[estimate] report -> {rel_path(REPORT_PATH)}")

    if summary["over_limit"]:
        log("[abort] estimate exceeds limit; no assets downloaded.")
        return

    if not args.download:
        log("[done] estimate only; pass --download to fetch assets.")
        return

    log("[download] estimate is within limit; downloading high-value assets...")
    download_assets(assets, args.max_single_bytes, sleep_seconds=args.sleep, workers=args.workers)
    final_summary = summarize(assets, discarded, references, args.limit_bytes)
    index = {
        "summary": final_summary,
        "assets": assets,
        "discarded_reference_count": len(discarded),
        "discarded_reason_counts": final_summary["discarded_reason_counts"],
    }
    write_json(INDEX_PATH, index)
    log(f"[download] index -> {rel_path(INDEX_PATH)}")


if __name__ == "__main__":
    main()
