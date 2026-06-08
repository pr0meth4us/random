#!/usr/bin/env python3
"""
Compress batch of images and show TOTAL combined base64 character count.
For APIs that require all images in a single field with a character limit.

Usage:
  python total_batch_compress.py ./photos --total-limit 50000
  python total_batch_compress.py ./photos --total-limit 50000 --max-dim 400 --quality 40
"""

import argparse
import base64
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "numpy", "--quiet"])
    from PIL import Image
    import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}


def encode_image(img: Image.Image, fmt: str, quality: int) -> bytes:
    """Encode image to bytes with specified quality."""
    buf = BytesIO()
    
    if fmt == "jpeg":
        img_save = img.convert("RGB")
        img_save.save(buf, format="JPEG", quality=quality, optimize=True, subsampling=0)
    elif fmt == "webp":
        img.save(buf, format="WebP", quality=quality, method=6)
    elif fmt == "png":
        compress = max(0, min(9, 9 - round(quality / 100 * 9)))
        img.save(buf, format="PNG", compress_level=compress, optimize=True)
    
    buf.seek(0)
    return buf.getvalue()


def process_image(args: tuple) -> dict:
    """Process single image: compress and return base64 stats."""
    src_path, fmt, quality, max_dim = args

    result = {
        "file": src_path.name,
        "error": None,
    }

    try:
        img = Image.open(src_path)
        
        # EXIF orientation
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Convert if needed
        if fmt == "jpeg" and img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode == "P":
            img = img.convert("RGBA")

        # Downscale if needed
        w, h = img.size
        if max_dim and max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            w, h = round(w * scale), round(h * scale)
            img = img.resize((w, h), Image.LANCZOS)

        # Compress
        data = encode_image(img, fmt, quality)
        b64_str = base64.b64encode(data).decode()

        result.update({
            "compressed_bytes": len(data),
            "base64_chars": len(b64_str),
            "resolution": f"{w}×{h}",
            "base64": b64_str,
        })

    except Exception as e:
        result["error"] = str(e)

    return result


def collect_images(folder: Path) -> list[Path]:
    """Recursively find all images."""
    return sorted(
        p for p in folder.rglob("*")
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
    )


def main():
    parser = argparse.ArgumentParser(
        description="Batch compress images — show TOTAL combined base64 char count",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python total_batch_compress.py ./photos --total-limit 50000
  python total_batch_compress.py ./photos --total-limit 50000 --max-dim 400 --quality 40
  python total_batch_compress.py ./photos --total-limit 50000 --max-dim 600 --quality 50
        """
    )
    parser.add_argument("input", help="Input folder containing images")
    parser.add_argument("--total-limit", type=int, required=True, help="Total character limit for ALL images combined")
    parser.add_argument("--max-dim", type=int, default=400, help="Max longest edge in pixels (default: 400)")
    parser.add_argument("--format", default="webp", choices=["jpeg", "webp", "png"])
    parser.add_argument("--quality", type=int, default=40, help="Quality 1-100 (default: 40)")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers")
    args = parser.parse_args()

    input_root = Path(args.input).resolve()
    if not input_root.is_dir():
        sys.exit(f"Error: {input_root} is not a directory")

    images = collect_images(input_root)
    if not images:
        sys.exit(f"No images found in {input_root}")

    print(f"\n{'='*80}")
    print(f"Compressing {len(images)} images")
    print(f"Total limit: {args.total_limit:,} characters")
    print(f"Per-image settings: {args.max_dim}px max, quality {args.quality}, {args.format}")
    print(f"{'='*80}\n")

    tasks = [
        (src, args.format, args.quality, args.max_dim)
        for src in images
    ]

    workers = args.workers or min(4, len(tasks))
    results = []

    if workers == 1 or len(tasks) == 1:
        for i, task in enumerate(tasks, 1):
            r = process_image(task)
            status = "✓" if not r.get("error") else "✗"
            print(f"[{i}/{len(tasks)}] {status} {r['file']:<45} {r.get('base64_chars', 'ERR'):>7,} chars")
            results.append(r)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(process_image, t): t for t in tasks}
            done = 0
            for future in as_completed(futures):
                done += 1
                r = future.result()
                status = "✓" if not r.get("error") else "✗"
                print(f"[{done}/{len(tasks)}] {status} {r['file']:<45} {r.get('base64_chars', 'ERR'):>7,} chars")
                results.append(r)

    # Calculate totals
    ok = [r for r in results if not r.get("error")]
    errs = [r for r in results if r.get("error")]
    
    total_chars = sum(r.get("base64_chars", 0) for r in ok)
    total_bytes = sum(r.get("compressed_bytes", 0) for r in ok)
    
    # Report
    print(f"\n{'='*80}")
    print(f"Individual images (sorted by size):")
    print(f"{'='*80}")
    
    col_w = [45, 12, 12]
    print(f"{'File':<{col_w[0]}} {'Chars':>{col_w[1]}} {'Bytes':>{col_w[2]}}")
    print("─" * sum(col_w))
    
    for r in sorted(ok, key=lambda x: x.get("base64_chars", 0), reverse=True):
        name = r["file"]
        if len(name) > col_w[0] - 1:
            name = "…" + name[-(col_w[0]-2):]
        chars = r.get("base64_chars", 0)
        compressed = r.get("compressed_bytes", 0)
        print(f"{name:<{col_w[0]}} {chars:>{col_w[1]},} {compressed:>{col_w[2]},}")
    
    print("─" * sum(col_w))
    print(f"{'TOTAL':<{col_w[0]}} {total_chars:>{col_w[1]},} {total_bytes:>{col_w[2]},}")
    
    # Pass/fail
    print(f"\n{'='*80}")
    if total_chars <= args.total_limit:
        headroom = args.total_limit - total_chars
        pct = 100 * headroom / args.total_limit
        print(f"✓ PASS — {total_chars:,} chars is under {args.total_limit:,} limit")
        print(f"  Headroom: {headroom:,} chars ({pct:.1f}% of limit)")
    else:
        over = total_chars - args.total_limit
        pct = 100 * over / args.total_limit
        print(f"✗ FAIL — {total_chars:,} chars exceeds {args.total_limit:,} limit by {over:,} chars ({pct:.1f}%)")
        print(f"\n  To fit, you need to:")
        print(f"  • Lower --quality (current: {args.quality})")
        print(f"  • Lower --max-dim (current: {args.max_dim}px)")
        print(f"  • Remove some images")
        
        # Suggest a quality reduction
        reduction_needed = total_chars / args.total_limit
        suggested_quality = max(10, int(args.quality / reduction_needed))
        print(f"\n  Try: --quality {suggested_quality} --max-dim {args.max_dim}")
    
    if errs:
        print(f"\n⚠ ERRORS ({len(errs)})")
        for r in errs:
            print(f"  {r['file']}: {r['error']}")
    
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()