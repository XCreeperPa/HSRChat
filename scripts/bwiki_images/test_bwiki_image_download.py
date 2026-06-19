import argparse
import hashlib
import html
import json
import mimetypes
import re
import socket
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
WIKI_DIR = ROOT_DIR / "references" / "wiki"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "references" / "bwiki_images" / "test_assets"
DEFAULT_INDEX_PATH = ROOT_DIR / "references" / "bwiki_images" / "test_index.json"
API_URL = "https://wiki.biligame.com/sr/api.php"

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

TARGET_KINDS = [
    "picture_zoom",
    "file_link",
    "dialog_image",
    "filepath_template",
    "special_file_path",
    "direct_url",
    "small_file_icon",
]

socket.setdefaulttimeout(20)


def clean_filename(name):
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    cleaned = re.sub(r"[\x00-\x1f]", "_", cleaned)
    return cleaned or "unnamed"


def normalize_file_ref(value):
    value = html.unescape(urllib.parse.unquote(value)).strip()
    value = re.sub(r"^(?:File|file|文件):", "", value).strip()
    return value


def looks_like_small_icon(line):
    sizes = [int(size) for size in re.findall(r"\|(\d{1,3})px(?:\||\])", line, flags=re.I)]
    if sizes and max(sizes) <= 64:
        return True
    return "{{图标|" in line


def rel_path(path):
    return path.relative_to(ROOT_DIR).as_posix()


def make_candidate(kind, match, path, lines, line_index):
    line = lines[line_index]
    original_ref = match.group(0)

    if kind == "direct_url":
        resolved_url = original_ref
        parsed = urllib.parse.urlparse(resolved_url)
        file_name = Path(urllib.parse.unquote(parsed.path)).name
    else:
        resolved_url = None
        file_name = normalize_file_ref(match.group(1))

    asset_kind = kind
    if kind == "file_link" and looks_like_small_icon(line):
        asset_kind = "small_file_icon"

    wiki_rel = path.relative_to(WIKI_DIR)
    parts = wiki_rel.parts
    context_before = lines[line_index - 1].strip() if line_index > 0 else ""
    context_after = lines[line_index + 1].strip() if line_index + 1 < len(lines) else ""

    identity = f"{asset_kind}\n{rel_path(path)}\n{line_index + 1}\n{original_ref}"
    return {
        "id": hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16],
        "source": "bwiki_image",
        "asset_kind": asset_kind,
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


def collect_candidates(per_type):
    selected = {kind: [] for kind in TARGET_KINDS}
    seen = set()

    for path in sorted(WIKI_DIR.rglob("*.txt")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_index, line in enumerate(lines):
            for kind, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    candidate = make_candidate(kind, match, path, lines, line_index)
                    asset_kind = candidate["asset_kind"]
                    if asset_kind not in selected:
                        continue
                    key = (asset_kind, candidate["file_name"], candidate["resolved_url"])
                    if key in seen or len(selected[asset_kind]) >= per_type:
                        continue
                    seen.add(key)
                    selected[asset_kind].append(candidate)

            if all(len(selected[kind]) >= per_type for kind in TARGET_KINDS):
                return selected

    return selected


def request_json(params, retries=2):
    query = urllib.parse.urlencode(params)
    url = f"{API_URL}?{query}"
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"API request failed: {exc}") from exc
            time.sleep((attempt + 1) * 1.5)
    return None


def resolve_image_info(file_name):
    data = request_json(
        {
            "action": "query",
            "titles": f"File:{file_name}",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|sha1|timestamp",
            "format": "json",
            "utf8": "1",
        }
    )
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        imageinfo = page.get("imageinfo") or []
        if imageinfo:
            info = dict(imageinfo[0])
            info["pageid"] = page.get("pageid")
            info["title"] = page.get("title")
            return info
    raise RuntimeError(f"No imageinfo found for {file_name}")


def download_bytes(url, max_bytes, retries=2):
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=20) as response:
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
            time.sleep((attempt + 1) * 1.5)
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
        width, height = struct.unpack(">II", data[16:24])
        return width, height

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
    suffix = Path(file_name).suffix
    if suffix:
        return file_name
    guessed = mimetypes.guess_extension(mime or "")
    return f"{file_name}{guessed or '.img'}"


def download_candidate(candidate, output_dir, max_bytes):
    result = dict(candidate)
    result.update(
        {
            "download_status": "pending",
            "local_path": None,
            "mime": None,
            "width": None,
            "height": None,
            "bytes": None,
            "sha1": None,
            "sha256": None,
            "error": None,
        }
    )

    try:
        image_info = None
        if candidate["resolved_url"]:
            resolved_url = candidate["resolved_url"]
        else:
            image_info = resolve_image_info(candidate["file_name"])
            resolved_url = image_info["url"]

        if image_info and image_info.get("size", 0) > max_bytes:
            result["download_status"] = "skipped_max_bytes"
            result["resolved_url"] = resolved_url
            result["bytes"] = image_info.get("size")
            result["error"] = f"remote file is larger than max_bytes: {image_info.get('size')}"
            return result

        data, headers, final_url = download_bytes(resolved_url, max_bytes=max_bytes)
        if not data or not is_image_bytes(data):
            raise RuntimeError("response did not look like an image")

        mime = (image_info or {}).get("mime") or headers.get("Content-Type", "").split(";")[0]
        width = (image_info or {}).get("width")
        height = (image_info or {}).get("height")
        if not width or not height:
            width, height = infer_dimensions(data)

        output_name = ensure_extension(clean_filename(candidate["file_name"]), mime)
        output_path = output_dir / candidate["asset_kind"] / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)

        result.update(
            {
                "download_status": "ok",
                "resolved_url": final_url,
                "local_path": rel_path(output_path),
                "mime": mime,
                "width": width,
                "height": height,
                "bytes": len(data),
                "sha1": (image_info or {}).get("sha1"),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bwiki_file_title": (image_info or {}).get("title"),
                "bwiki_file_timestamp": (image_info or {}).get("timestamp"),
            }
        )
    except Exception as exc:
        result["download_status"] = "failed"
        result["error"] = str(exc)

    return result


def main():
    parser = argparse.ArgumentParser(description="Download a tiny mixed sample of BWiki image references.")
    parser.add_argument("--per-type", type=int, default=1, help="number of samples to download per image kind")
    parser.add_argument(
        "--kinds",
        default=",".join(TARGET_KINDS),
        help=f"comma-separated image kinds to test; valid values: {', '.join(TARGET_KINDS)}",
    )
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024, help="maximum bytes per image")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="directory for downloaded test images")
    parser.add_argument("--index", default=str(DEFAULT_INDEX_PATH), help="path for generated test index JSON")
    parser.add_argument("--sleep", type=float, default=0.5, help="delay between downloads")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    index_path = Path(args.index).resolve()
    requested_kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    unknown_kinds = sorted(set(requested_kinds) - set(TARGET_KINDS))
    if unknown_kinds:
        raise SystemExit(f"Unknown image kinds: {', '.join(unknown_kinds)}")

    selected = collect_candidates(args.per_type)
    entries = []

    for kind in requested_kinds:
        candidates = selected.get(kind, [])
        if not candidates:
            print(f"[miss] {kind}: no local reference found", flush=True)
            continue
        for candidate in candidates:
            result = download_candidate(candidate, output_dir, args.max_bytes)
            entries.append(result)
            status = result["download_status"]
            path = result.get("local_path") or result.get("resolved_url") or ""
            print(f"[{status}] {kind}: {candidate['file_name']} -> {path}", flush=True)
            time.sleep(args.sleep)

    index = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "test_download",
        "per_type": args.per_type,
        "max_bytes": args.max_bytes,
        "output_dir": rel_path(output_dir),
        "entries": entries,
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[index] wrote {len(entries)} entries to {rel_path(index_path)}", flush=True)


if __name__ == "__main__":
    main()
