#!/usr/bin/env python3
"""
spot_the_difference.py  (v3 — universal edition)
=================================================
Automatic spot-the-difference detector that works for both:
  • Colour photo puzzles  (tropical island, etc.)
  • B&W line-drawing puzzles  (jungle animals, etc.)

The script auto-detects which mode to use based on image colour variance.

Key design decisions vs earlier versions:
  ┌─────────────────────┬────────────────┬──────────────────────────────────────┐
  │ Parameter           │ Colour mode    │ Line-drawing mode                    │
  ├─────────────────────┼────────────────┼──────────────────────────────────────┤
  │ SSIM threshold      │ Otsu (auto)    │ 30 (fixed)                           │
  │ Morph kernel        │ 9px            │ 3px  (don't bridge small diffs)      │
  │ delta_floor         │ 8.0            │ 5.0                                  │
  │ max_diff_min        │ —              │ 150  (kill alignment artifacts)       │
  │ NMS radius          │ —              │ 80px                                 │
  └─────────────────────┴────────────────┴──────────────────────────────────────┘

  max_diff_min is the KEY insight for line drawings:
    - SIFT warp residuals (false positives) peak at ~100 pixel diff
    - Real ink differences always peak at 200+
    - threshold=150 perfectly separates the two

Usage:
  python spot_the_difference.py puzzle.jpg               # combined image
  python spot_the_difference.py img1.jpg img2.jpg        # two separate images
  python spot_the_difference.py img1.jpg img2.jpg --output result.png
  python spot_the_difference.py img1.jpg img2.jpg --mode line
  python spot_the_difference.py img1.jpg img2.jpg --mode colour

Install once:
  pip install opencv-python scikit-image numpy pillow
"""

import sys
import argparse
import warnings
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
#  TUNING CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Colour-photo mode (tropical island puzzle etc.)
COLOUR_SSIM_THRESH  = None   # None = use Otsu
COLOUR_MORPH_KSIZE  = 9
COLOUR_MIN_AREA     = 50
COLOUR_DELTA_FLOOR  = 8.0
COLOUR_MAX_DIFF_MIN = 0      # disabled for colour
COLOUR_NMS_RADIUS   = 0      # disabled for colour (use auto-gap threshold)

# Line-drawing mode (B&W sketch puzzles etc.)
LINE_SSIM_THRESH    = 30
LINE_MORPH_KSIZE    = 3
LINE_MIN_AREA       = 20
LINE_DELTA_FLOOR    = 5.0
LINE_MAX_DIFF_MIN   = 150    # ← KEY: eliminates SIFT warp residuals
LINE_NMS_RADIUS     = 80

# Shared
SIFT_FEATURES  = 12000
LOWE_RATIO     = 0.78
RANSAC_THRESH  = 5.0
BORDER_FRAC    = 0.04

# Auto-detect threshold: images with mean saturation below this → line-drawing mode
SATURATION_THRESHOLD = 20


# ─────────────────────────────────────────────────────────────────────────────
#  IMAGE I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_bgr(path: str) -> np.ndarray:
    """Load any format as plain BGR uint8."""
    return cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)


def auto_slice(img: np.ndarray):
    """Split combined puzzle image into two equal halves."""
    h, w = img.shape[:2]
    if h > w:
        half = h // 2
        a, b = img[:half], img[h - half:]
    else:
        half = w // 2
        a, b = img[:, :half], img[:, w - half:]
    print(f"[INFO] Auto-sliced → A{a.shape[:2]}  B{b.shape[:2]}")
    return a, b


def gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def is_line_drawing(img: np.ndarray) -> bool:
    """Return True if image appears to be a B&W line drawing (low saturation)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mean_sat = float(hsv[:, :, 1].mean())
    print(f"[INFO] Mean saturation: {mean_sat:.1f}  "
          f"→ {'line-drawing' if mean_sat < SATURATION_THRESHOLD else 'colour'} mode")
    return mean_sat < SATURATION_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
#  SIFT ALIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

def align_sift(ref: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """Align tgt to ref using SIFT → AKAZE → ORB fallback chain."""
    h, w = ref.shape[:2]

    for name in ("SIFT", "AKAZE", "ORB"):
        if   name == "SIFT":  det, norm = cv2.SIFT_create(nfeatures=SIFT_FEATURES), cv2.NORM_L2
        elif name == "AKAZE": det, norm = cv2.AKAZE_create(),                        cv2.NORM_HAMMING
        else:                 det, norm = cv2.ORB_create(nfeatures=SIFT_FEATURES),   cv2.NORM_HAMMING

        kp1, d1 = det.detectAndCompute(gray(ref), None)
        kp2, d2 = det.detectAndCompute(gray(tgt), None)
        if d1 is None or d2 is None or len(kp1) < 8 or len(kp2) < 8:
            continue

        matcher = cv2.BFMatcher(norm, crossCheck=False)
        raw  = matcher.knnMatch(d2, d1, k=2)
        good = [m for m, n in raw
                if len((m, n)) == 2 and m.distance < LOWE_RATIO * n.distance]
        print(f"[INFO] {name}: {len(good)} good matches")
        if len(good) < 12:
            continue

        src = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, RANSAC_THRESH)
        if H is None:
            continue

        inliers = int(mask.sum()) if mask is not None else 0
        print(f"[INFO] {name}: homography accepted ({inliers} inliers)")
        return cv2.warpPerspective(tgt, H, (w, h),
                                   flags=cv2.INTER_LANCZOS4,
                                   borderMode=cv2.BORDER_REFLECT_101)

    print("[WARN] All detectors failed — falling back to raw resize")
    return cv2.resize(tgt, (w, h), interpolation=cv2.INTER_LANCZOS4)


# ─────────────────────────────────────────────────────────────────────────────
#  DETECTION — LINE-DRAWING MODE
# ─────────────────────────────────────────────────────────────────────────────

def _auto_gap_threshold(deltas: list, floor: float):
    """Find natural noise/signal boundary (used in colour mode)."""
    if len(deltas) < 3:
        return floor, "too few — using floor"
    s    = sorted(deltas)
    gaps = [s[i + 1] - s[i] for i in range(len(s) - 1)]
    top2 = sorted(gaps, reverse=True)[:2]
    idx  = int(np.argmax(gaps))
    nc, sc = idx + 1, len(s) - idx - 1
    dominant = (top2[0] > 20.0
                and (len(top2) < 2 or top2[0] >= 2.0 * top2[1])
                and nc >= 1 and sc >= 1)
    if dominant:
        t = (s[idx] + s[idx + 1]) / 2.0
        return t, f"dominant gap {s[idx]:.1f}→{s[idx+1]:.1f}"
    return floor, f"no dominant gap — floor {floor:.1f}"


def detect_line(img_a: np.ndarray, img_b: np.ndarray) -> tuple:
    """
    Detection pipeline for B&W line-drawing puzzles.

    Critical filter — max_diff_min:
      SIFT warp residuals (false positives) are smooth, low-amplitude blurs.
      Their peak pixel diff sits around 100.
      Real ink line differences are sharp and peak at 200+.
      Threshold at 150 separates them cleanly.
    """
    h, w = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)

    score, diff = ssim(gray(img_a), gray(img_b), full=True)
    print(f"[INFO] SSIM: {score:.4f}")

    inv = cv2.bitwise_not((diff * 255).clip(0, 255).astype(np.uint8))

    # Fixed threshold — Otsu merges small adjacent line-diffs into one big blob
    _, thresh = cv2.threshold(inv, LINE_SSIM_THRESH, 255, cv2.THRESH_BINARY)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                  (LINE_MORPH_KSIZE, LINE_MORPH_KSIZE))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k)

    border = max(10, int(min(h, w) * BORDER_FRAC))
    bmask  = np.zeros_like(thresh)
    bmask[border:h - border, border:w - border] = 255
    thresh = cv2.bitwise_and(thresh, bmask)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cdiff = np.mean(cv2.absdiff(img_a, img_b).astype(np.float32), axis=2)
    ga    = gray(img_a).astype(np.float64)
    gb    = gray(img_b).astype(np.float64)

    candidates = []
    for cnt in contours:
        if cv2.contourArea(cnt) < LINE_MIN_AREA:
            continue
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, cv2.FILLED)
        delta = cv2.mean(cdiff, mask=mask)[0]
        if delta < LINE_DELTA_FLOOR:
            continue

        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        cx, cy, r = int(cx), int(cy), int(r)

        x1, y1 = max(0, cx - r - 5), max(0, cy - r - 5)
        x2, y2 = min(w, cx + r + 5), min(h, cy + r + 5)
        max_diff = float(np.abs(ga[y1:y2, x1:x2] - gb[y1:y2, x1:x2]).max())

        # ← THE KEY FILTER
        if max_diff < LINE_MAX_DIFF_MIN:
            print(f"       skip ({cx},{cy}) max_diff={max_diff:.0f} < {LINE_MAX_DIFF_MIN} (alignment artifact)")
            continue

        candidates.append((cx, cy, max(r + 15, 18), delta))

    print(f"[INFO] Candidates after filtering: {len(candidates)}")
    deltas = sorted(d for _, _, _, d in candidates)
    print(f"[INFO] Deltas: {[round(d, 1) for d in deltas]}")

    # Non-maximum suppression
    candidates_sorted = sorted(candidates, key=lambda x: -x[3])
    kept = []
    for cx, cy, r, d in candidates_sorted:
        if not any(((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5 < LINE_NMS_RADIUS
                   for kx, ky, _, _ in kept):
            kept.append((cx, cy, r, d))

    result = img_b.copy()
    for cx, cy, r, _ in kept:
        cv2.circle(result, (cx, cy), r, (0, 0, 255), 2)

    return result, len(kept)


# ─────────────────────────────────────────────────────────────────────────────
#  DETECTION — COLOUR MODE
# ─────────────────────────────────────────────────────────────────────────────

def detect_colour(img_a: np.ndarray, img_b: np.ndarray) -> tuple:
    """Detection pipeline for colour photo puzzles."""
    h, w = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)

    score, diff = ssim(gray(img_a), gray(img_b), full=True)
    print(f"[INFO] SSIM: {score:.4f}")

    inv = cv2.bitwise_not((diff * 255).clip(0, 255).astype(np.uint8))
    _, thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k9)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k5)

    border = max(10, int(min(h, w) * BORDER_FRAC))
    bmask  = np.zeros_like(thresh)
    bmask[border:h - border, border:w - border] = 255
    thresh = cv2.bitwise_and(thresh, bmask)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cdiff = np.mean(cv2.absdiff(img_a, img_b).astype(np.float32), axis=2)

    candidates = []
    for cnt in contours:
        if cv2.contourArea(cnt) < COLOUR_MIN_AREA:
            continue
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(mask, [cnt], -1, 255, cv2.FILLED)
        delta = cv2.mean(cdiff, mask=mask)[0]
        candidates.append((cnt, delta))

    if not candidates:
        print("[WARN] No candidates found.")
        return img_b.copy(), 0

    deltas = sorted(d for _, d in candidates)
    print(f"[INFO] Candidates: {len(candidates)}  "
          f"deltas: {[round(d, 1) for d in deltas]}")

    threshold, reason = _auto_gap_threshold(deltas, COLOUR_DELTA_FLOOR)
    print(f"[INFO] Δ-threshold: {threshold:.1f}  ({reason})")

    result = img_b.copy()
    count  = 0
    for cnt, delta in candidates:
        if delta < threshold:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(cnt)
        r = max(int(radius) + 12, 18)
        cv2.circle(result, (int(cx), int(cy)), r, (0, 0, 255), 3)
        count += 1

    return result, count


# ─────────────────────────────────────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Universal spot-the-difference detector (colour + line-drawing).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py img1.jpg img2.jpg
  python spot_the_difference.py img1.jpg img2.jpg --output result.png
  python spot_the_difference.py img1.jpg img2.jpg --mode line
  python spot_the_difference.py img1.jpg img2.jpg --no-align
        """,
    )
    p.add_argument("images",     nargs="+", metavar="IMAGE")
    p.add_argument("--output",   default="circled_result.png")
    p.add_argument("--mode",     choices=["auto", "colour", "line"], default="auto",
                   help="Force detection mode (default: auto-detect)")
    p.add_argument("--no-align", action="store_true", help="Skip SIFT alignment")
    return p.parse_args()


def main():
    args = parse_args()

    if len(args.images) == 1:
        print(f"[INFO] Single image → auto-slicing: {args.images[0]!r}")
        combined = load_bgr(args.images[0])
        img_a, img_b = auto_slice(combined)
    elif len(args.images) == 2:
        print(f"[INFO] Two images: {args.images[0]!r}  vs  {args.images[1]!r}")
        img_a = load_bgr(args.images[0])
        img_b = load_bgr(args.images[1])
    else:
        sys.exit("[ERROR] Provide 1 combined image or 2 separate images.")

    print(f"[INFO] A: {img_a.shape[:2]}   B: {img_b.shape[:2]}")

    if args.no_align:
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]),
                           interpolation=cv2.INTER_LANCZOS4)
        print("[INFO] Alignment skipped (--no-align)")
    else:
        img_b = align_sift(img_a, img_b)

    # Mode selection
    if args.mode == "auto":
        line_mode = is_line_drawing(img_a)
    else:
        line_mode = (args.mode == "line")
        print(f"[INFO] Mode forced: {'line-drawing' if line_mode else 'colour'}")

    if line_mode:
        result, count = detect_line(img_a, img_b)
    else:
        result, count = detect_colour(img_a, img_b)

    cv2.imwrite(args.output, result)

    print()
    print("=" * 45)
    print(f"  Mode              : {'line-drawing' if line_mode else 'colour'}")
    print(f"  Differences found : {count}")
    print(f"  Saved to          : {args.output!r}")
    print("=" * 45)


if __name__ == "__main__":
    main()