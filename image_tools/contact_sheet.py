"""Tile many images into numbered contact sheets for fast visual review (macOS: uses sips, so HEIC works).

    printf '%s\n' a.heic b.jpg ... | python3 contact_sheet.py OUT_DIR [--cols 8] [--rows 6] [--thumb 240]

Writes OUT_DIR/sheet_001.jpg, ... and OUT_DIR/index.tsv (sheet, number, path).
The number printed on each tile is its line in index.tsv, counting from 1.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont, ImageOps

LABEL_HEIGHT = 22
SIPS_WORKERS = 8


def make_thumb(args):
    src, out, size = args
    result = subprocess.run(["sips", "-Z", str(size), "-s", "format", "jpeg", src, "--out", out], capture_output=True)
    return out if result.returncode == 0 and os.path.exists(out) else None


def build_sheets(paths, out_dir, cols, rows, size):
    os.makedirs(out_dir, exist_ok=True)
    font = ImageFont.load_default(size=16)
    per_sheet = cols * rows
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [(p, os.path.join(tmp, f"{i}.jpg"), size) for i, p in enumerate(paths)]
        with ThreadPoolExecutor(SIPS_WORKERS) as pool:
            thumbs = list(pool.map(make_thumb, jobs))
        with open(os.path.join(out_dir, "index.tsv"), "w") as index:
            for start in range(0, len(paths), per_sheet):
                sheet_no = start // per_sheet + 1
                sheet = Image.new("RGB", (cols * size, rows * (size + LABEL_HEIGHT)), "white")
                draw = ImageDraw.Draw(sheet)
                for slot, i in enumerate(range(start, min(start + per_sheet, len(paths)))):
                    x, y = slot % cols * size, slot // cols * (size + LABEL_HEIGHT)
                    if thumbs[i]:
                        with Image.open(thumbs[i]) as raw:
                            im = ImageOps.exif_transpose(raw)  # sips keeps the rotation tag but not the rotation
                            sheet.paste(im, (x + (size - im.width) // 2, y + LABEL_HEIGHT + (size - im.height) // 2))
                    else:
                        draw.text((x + 4, y + LABEL_HEIGHT + 4), "unreadable", fill="red", font=font)
                    draw.text((x + 4, y + 2), f"{i + 1} {os.path.basename(paths[i])}", fill="black", font=font)
                    index.write(f"{sheet_no}\t{i + 1}\t{paths[i]}\n")
                sheet.save(os.path.join(out_dir, f"sheet_{sheet_no:03d}.jpg"), quality=80)
    return -(-len(paths) // per_sheet)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("out_dir")
    p.add_argument("--cols", type=int, default=8)
    p.add_argument("--rows", type=int, default=6)
    p.add_argument("--thumb", type=int, default=240, help="tile size in pixels")
    a = p.parse_args()
    paths = [line.rstrip("\n") for line in sys.stdin if line.strip()]
    if not paths:
        p.error("no image paths on stdin")
    print(f"{build_sheets(paths, a.out_dir, a.cols, a.rows, a.thumb)} sheets for {len(paths)} images -> {a.out_dir}")


if __name__ == "__main__":
    main()
