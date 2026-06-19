import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
BWiki_DIR = ROOT_DIR / "references" / "bwiki_images"
ASSETS_DIR = BWiki_DIR / "assets"
ASSETS_WEBP_DIR = BWiki_DIR / "assets_webp"
SYNC_SCRIPT = SCRIPT_DIR / "sync_bwiki_images.py"
COMPRESS_SCRIPT = SCRIPT_DIR / "compress_bwiki_images.py"


DEFAULT_NET_WORKERS = max(4, min(32, (os.cpu_count() or 4) * 4))
DEFAULT_CPU_WORKERS = max(1, os.cpu_count() or 1)


def log(message):
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        safe_message = message.encode("ascii", errors="backslashreplace").decode("ascii")
        print(safe_message, flush=True)


def remove_dir(path, retries=5):
    if path.exists():
        log(f"[clean] remove {path.relative_to(ROOT_DIR).as_posix()}")
        for attempt in range(1, retries + 1):
            try:
                shutil.rmtree(path)
                return
            except PermissionError as exc:
                if attempt == retries:
                    raise
                log(f"[clean] locked file, retry {attempt}/{retries}: {exc}")
                time.sleep(2)


def run_step(args):
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    log("[run] " + " ".join(str(part) for part in args))
    process = subprocess.Popen(
        args,
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    return process.wait()


def main():
    parser = argparse.ArgumentParser(description="Run BWiki image discovery, download, and WebP compression.")
    parser.add_argument("--clean", action="store_true", help="remove original and compressed image caches before running")
    parser.add_argument("--clean-compressed", action="store_true", help="remove compressed WebP cache before running")
    parser.add_argument("--network-workers", type=int, default=DEFAULT_NET_WORKERS, help="parallel workers for estimate/download")
    parser.add_argument("--compress-workers", type=int, default=DEFAULT_CPU_WORKERS, help="parallel workers for WebP compression")
    parser.add_argument("--limit-bytes", type=int, default=1024 * 1024 * 1024, help="abort download above estimated total bytes")
    parser.add_argument("--max-single-bytes", type=int, default=64 * 1024 * 1024, help="max bytes for one original image")
    parser.add_argument("--sleep", type=float, default=0.0, help="delay between completed network tasks")
    parser.add_argument("--no-overwrite-compressed", action="store_true", help="reuse existing compressed files")
    args = parser.parse_args()

    if args.clean:
        remove_dir(ASSETS_DIR)
        remove_dir(ASSETS_WEBP_DIR)
    elif args.clean_compressed:
        remove_dir(ASSETS_WEBP_DIR)

    sync_cmd = [
        sys.executable,
        str(SYNC_SCRIPT),
        "--download",
        "--workers",
        str(args.network_workers),
        "--limit-bytes",
        str(args.limit_bytes),
        "--max-single-bytes",
        str(args.max_single_bytes),
        "--sleep",
        str(args.sleep),
    ]
    sync_code = run_step(sync_cmd)
    if sync_code != 0:
        log(f"[error] sync step exited with code {sync_code}")
        return sync_code

    compress_cmd = [
        sys.executable,
        str(COMPRESS_SCRIPT),
        "--workers",
        str(args.compress_workers),
    ]
    if not args.no_overwrite_compressed:
        compress_cmd.append("--overwrite")

    compress_code = run_step(compress_cmd)
    if compress_code != 0:
        log(f"[error] compress step exited with code {compress_code}")
        return compress_code

    log("[done] BWiki image pipeline completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
