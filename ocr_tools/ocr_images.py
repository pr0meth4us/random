"""OCR a list of photos (HEIC/JPG/PNG) with Cloud Vision into a JSONL cache.

    printf '%s\n' a.heic b.jpg ... | python3 ocr_images.py OUT.jsonl [--max-side 2000] [--workers 8]
    python3 ocr_images.py --selftest

Each line of OUT.jsonl is {"path": ..., "text": ...}. Paths already in OUT.jsonl are
skipped, so an interrupted or repeated run never pays for the same image twice.
Images are shrunk to --max-side and sent as JPEG (sips, macOS), since Vision does not
take HEIC. Vision client and credentials come from bifrost via ocr_tools.pdf_ocr.
Failures are reported on stderr and not cached, so a rerun retries them.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ocr_tools.pdf_ocr import _default_vision_client, ocr_image  # noqa: E402

PROGRESS_EVERY = 50


def done_paths(jsonl_path):
    if not os.path.exists(jsonl_path):
        return set()
    with open(jsonl_path, encoding="utf-8") as f:
        return {json.loads(line)["path"] for line in f if line.strip()}


def to_jpeg(path, max_side, tmp_dir):
    out = os.path.join(tmp_dir, f"{threading.get_ident()}.jpg")
    # close_fds=False lets Python posix_spawn instead of fork; forking while gRPC threads run crashes the child.
    result = subprocess.run(["sips", "-Z", str(max_side), "-s", "format", "jpeg", path, "--out", out], capture_output=True, close_fds=False)
    if result.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"sips could not convert: {result.stderr.decode(errors='replace').strip()}")
    with open(out, "rb") as f:
        data = f.read()
    os.remove(out)
    return data


def run(paths, out_path, max_side, workers):
    skip = done_paths(out_path)
    todo = [p for p in dict.fromkeys(paths) if p not in skip]
    print(f"{len(todo)} to OCR ({len(skip)} already in {out_path})", file=sys.stderr)
    if not todo:
        return 0
    client = _default_vision_client()
    lock = threading.Lock()
    stats = {"done": 0, "failed": 0}

    with tempfile.TemporaryDirectory() as tmp, open(out_path, "a", encoding="utf-8") as out:
        def work(path):
            try:
                text = ocr_image(to_jpeg(path, max_side, tmp), client)
            except Exception as e:  # report and keep going; uncached, so a rerun retries it
                with lock:
                    stats["failed"] += 1
                    print(f"  failed: {path} ({e})", file=sys.stderr)
                return
            with lock:
                out.write(json.dumps({"path": path, "text": text}, ensure_ascii=False) + "\n")
                out.flush()
                stats["done"] += 1
                if stats["done"] % PROGRESS_EVERY == 0:
                    print(f"  {stats['done']}/{len(todo)}", file=sys.stderr, flush=True)

        with ThreadPoolExecutor(workers) as pool:
            list(pool.map(work, todo))
    print(f"OCR'd {stats['done']}, failed {stats['failed']}", file=sys.stderr)
    return stats["failed"]


def selftest():
    with tempfile.TemporaryDirectory() as tmp:
        cache = os.path.join(tmp, "c.jsonl")
        assert done_paths(cache) == set()
        with open(cache, "w", encoding="utf-8") as f:
            f.write(json.dumps({"path": "/a.heic", "text": "x"}) + "\n\n")
        assert done_paths(cache) == {"/a.heic"}
        png = os.path.join(tmp, "p.png")
        subprocess.run(["sips", "-s", "format", "png", "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericDocumentIcon.icns", "--out", png], capture_output=True, check=True)
        assert to_jpeg(png, 64, tmp)[:2] == b"\xff\xd8", "converted to JPEG"
    print("selftest ok")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out", nargs="?", help="JSONL cache to append to")
    p.add_argument("--max-side", type=int, default=2000)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if not a.out:
        p.error("need OUT.jsonl")
    paths = [line.rstrip("\n") for line in sys.stdin if line.strip()]
    if not paths:
        p.error("no image paths on stdin")
    sys.exit(1 if run(paths, a.out, a.max_side, a.workers) else 0)


if __name__ == "__main__":
    main()
