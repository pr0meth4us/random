import argparse
from PIL import Image
import os

def compress_image(input_path, quality=85, max_width=1920):
    img = Image.open(input_path)

    # Resize if image is wider than max_width
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Convert to RGB for JPEG compatibility
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Determine format
    fmt = "JPEG" if input_path.lower().endswith((".jpg", ".jpeg")) else img.format

    # Save back to same file
    img.save(
        input_path,
        format=fmt,
        optimize=True,
        quality=quality,
        progressive=True if fmt == "JPEG" else False
    )
    print(f"✅ Compressed and saved: {input_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compress image in-place while preserving quality.")
    parser.add_argument("input", help="Path to input image (will be overwritten)")
    parser.add_argument("--quality", type=int, default=85, help="Compression quality (default: 85)")
    parser.add_argument("--max_width", type=int, default=1920, help="Resize if width exceeds this (default: 1920)")

    args = parser.parse_args()
    compress_image(args.input, args.quality, args.max_width)
