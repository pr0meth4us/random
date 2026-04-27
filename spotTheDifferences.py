#!/usr/bin/env python3
"""
spot_the_difference.py
======================
Automatic spot-the-difference detector with bulletproof 3-stage alignment.

── Alignment pipeline ──────────────────────────────────────────────────────
 Stage 1  Scale normalisation
            • Same size        → pass through unchanged
            • Same aspect ratio → Lanczos resize (no distortion)
            • Different ratio  → fit-inside with median-colour padding

 Stage 2  SIFT feature alignment  (AKAZE → ORB as fallbacks)
            • Finds keypoints, runs Lowe ratio test, computes RANSAC homography
            • Sanity-checks the homography (rejects wild warps)
            • Warps with REFLECT_101 border (kills the arc-artifact)

 Stage 3  ECC pixel-level refinement
            • findTransformECC polishes the warp to sub-pixel accuracy
            • Runs on a downscaled copy for speed
            • Only applied if it strictly improves SSIM

── Detection pipeline ──────────────────────────────────────────────────────
  SSIM difference map + CIE-Lab ΔE colour map (fused) → Otsu threshold
  → morphological cleanup → border mask → contour detection
  → colour-delta scoring → auto gap-threshold → contour grouping/merging
  → coloured circles on output

── Output ──────────────────────────────────────────────────────────────────
  Single combined image  → stacked layout preserved, circles on both panels,
                           Khmer caption banner at top.
  Two separate images    → side-by-side layout, Khmer caption banner at top.
  One random vivid colour chosen per run; numbered badge on every circle.

Usage:
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py original.png modified.png
  python spot_the_difference.py puzzle.jpg --output result.png
  python spot_the_difference.py puzzle.jpg --ecc      (ECC refinement, slower)
  python spot_the_difference.py puzzle.jpg --no-align (skip alignment)

Install once:
  pip install opencv-python scikit-image numpy pillow
"""

import sys
import argparse
import warnings
import random
import os
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
#  TUNING CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MAX_WARP_SCALE = 3.0   # reject homography if any axis scales by more than this
SAME_RATIO_TOL = 0.03  # treat aspect ratios within 3% as "same"
ECC_MAX_DIM    = 400   # ECC runs on a thumbnail — smaller = faster
ECC_MAX_ITER   = 150   # usually converges in <50 iters if it's going to work
ECC_EPS        = 1e-5


# ─────────────────────────────────────────────────────────────────────────────
#  FONTS  (for output annotation)
# ─────────────────────────────────────────────────────────────────────────────

# ── Known Khmer font paths across Linux / Windows / macOS ────────────────────
#
# IMPORTANT — why only Noto Khmer fonts are included here:
#   KhmerOS fonts use a legacy glyph-mapping encoding system, NOT Unicode
#   OpenType.  When PIL feeds them Unicode codepoints, the glyphs come out
#   scrambled ("ឃើ" → "យ៉ី" etc.).  Only fonts with proper Unicode OpenType
#   Khmer GSUB/GPOS tables render correctly; on a standard system those are
#   the Noto Khmer family.
#
# Linux:   sudo apt install fonts-noto-core
# Windows: https://fonts.google.com/noto/specimen/Noto+Sans+Khmer  → Install
# macOS:   brew install font-noto-sans-khmer  (tap homebrew/cask-fonts first)
_KHMER_FONT_CANDIDATES = [
    # ── Linux: Noto ───────────────────────────────────────────────────────────
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerifKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerifKhmer-Regular.ttf",
    # ── Windows ───────────────────────────────────────────────────────────────
    "C:/Windows/Fonts/NotoSansKhmer-Bold.ttf",
    "C:/Windows/Fonts/NotoSansKhmer-Regular.ttf",
    "C:/Windows/Fonts/NotoSerifKhmer-Bold.ttf",
    "C:/Windows/Fonts/NotoSerifKhmer-Regular.ttf",
    # ── macOS ─────────────────────────────────────────────────────────────────
    "/Library/Fonts/NotoSansKhmer-Bold.ttf",
    "/Library/Fonts/NotoSansKhmer-Regular.ttf",
    "/Library/Fonts/NotoSerifKhmer-Bold.ttf",
    "/Library/Fonts/NotoSerifKhmer-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/NotoSansKhmer-Bold.ttf"),
    os.path.expanduser("~/Library/Fonts/NotoSansKhmer-Regular.ttf"),
    # ── Homebrew / user-local ─────────────────────────────────────────────────
    "/usr/local/share/fonts/NotoSansKhmer-Bold.ttf",
    os.path.expanduser("~/.fonts/NotoSansKhmer-Bold.ttf"),
    os.path.expanduser("~/.local/share/fonts/NotoSansKhmer-Bold.ttf"),
    os.path.expanduser("~/.fonts/NotoSerifKhmer-Bold.ttf"),
    os.path.expanduser("~/.local/share/fonts/NotoSerifKhmer-Bold.ttf"),
]

# Build the list of fonts that actually exist on this machine
_AVAILABLE_KHMER_FONTS = [p for p in _KHMER_FONT_CANDIDATES if os.path.exists(p)]

if not _AVAILABLE_KHMER_FONTS:
    print(
        "[WARN] No Khmer fonts found.  Khmer text will fall back to the default font.\n"
        "       To fix, install fonts:\n"
        "         Linux : sudo apt install fonts-noto-core fonts-khmeros fonts-sil-mondulkiri\n"
        "         Windows : download from https://fonts.google.com/noto/specimen/Noto+Sans+Khmer\n"
        "         macOS : brew install font-noto-sans-khmer  (requires homebrew-cask-fonts)"
    )

_LATIN_FONT = next((p for p in [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "/Library/Fonts/Arial Bold.ttf",
] if os.path.exists(p)), None)


def pick_random_khmer_font(size: int):
    """
    Pick one Khmer font at random from all fonts found on this machine.
    Validates with the full range of Khmer characters used in the output
    (including Khmer digits ០-៩) — some fonts handle basic glyphs but
    crash on digit codepoints.  Skips any font that raises an error.
    Returns (ImageFont, path_str).  Falls back to PIL default if nothing works.
    """
    import PIL.Image as _PILImg, PIL.ImageDraw as _PILDraw
    # Use all character types that appear in the output
    test_text = "រកឃើញភាពខុសគ្នា ០១២៣៤៥៦៧៨៩ កន្លែង ចម្លើយពីក្មួយ និរន្ត"
    candidates = list(_AVAILABLE_KHMER_FONTS)  # copy so we can shuffle
    random.shuffle(candidates)
    for path in candidates:
        try:
            f   = ImageFont.truetype(path, size)
            _d  = _PILDraw.Draw(_PILImg.new("RGB", (800, 100)))
            _d.textbbox((0, 0), test_text, font=f)
            _d.text((0, 0), test_text, font=f, fill=(0, 0, 0))  # also test actual render
            return f, path
        except Exception:
            continue
    return ImageFont.load_default(), "default"


# ─────────────────────────────────────────────────────────────────────────────
#  1.  IMAGE I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_bgr(path: str) -> np.ndarray:
    """Load any format (TIFF, RGBA, WebP …) as plain BGR uint8."""
    return cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)


def _find_separator(profile: np.ndarray, axis_len: int) -> int | None:
    """
    Find where one puzzle image ends and the next begins.

    Problem: many puzzles have text, titles, or copyright notices between the
    two images.  Those rows aren't uniformly white — the text breaks up any
    contiguous bright band — so a simple "find a run of bright rows" approach
    picks a 2-pixel gap inside the text rather than the whole separator zone.

    Solution: smooth the row-brightness profile with a 60px box filter, then
    find the peak of the smoothed curve in the central 15–85% region.  The
    averaging blurs the text rows into one big bright hump, making the centre
    of the separator zone easy to locate.

    Falls back to None if the brightest hump isn't clearly brighter than the
    surrounding image content (which would mean there's no separator to find).
    """
    lo = int(axis_len * 0.15)
    hi = int(axis_len * 0.85)

    # 60-pixel box-filter smoothing (handles text rows gracefully)
    k        = 60
    kernel   = np.ones(k) / k
    smoothed = np.convolve(profile, kernel, mode='same')

    region     = smoothed[lo:hi]
    local_max  = float(region.max())
    local_mean = float(region.mean())

    # Only trust the separator if the peak is meaningfully brighter than average
    # (i.e. there actually IS a lighter gap between two content regions).
    # Threshold lowered to 5: text rows inside the gap band reduce the smoothed
    # peak, so the original 15 was too strict for puzzles like Afrika where
    # "Im unteren Bild sind 10 Fehler" sits inside the white separator.
    if local_max - local_mean < 5:
        return None

    sep_centre = lo + int(np.argmax(region))
    print(f"[INFO] Separator detected at smoothed peak y={sep_centre}  "
          f"(brightness {local_max:.0f} vs mean {local_mean:.0f})")
    return sep_centre


def auto_slice(img: np.ndarray):
    """
    Split a combined puzzle image into its two puzzle halves.

    Strategy (portrait images, h > w):
      1. Build a per-row mean-brightness profile.
      2. Detect the separator band (the white/light gap between the two puzzle
         images) using _find_separator.
      3. If found: cut at the separator centre so neither half contains the gap.
      4. If not found: fall back to the safe h//2 cut (same for even/odd sizes).

    Landscape images (w >= h) use the same logic on columns.

    The header ("FIND THE 5 DIFFERENCES" etc.) is automatically ignored because
    it sits in the top 20% of the image, outside the 20-80% search window.

    Returns
    -------
    a        : top/left panel  (BGR)
    b        : bottom/right panel  (BGR), same size as a
    a_start  : pixel offset of panel-a's top-left corner in the combined image
    b_start  : pixel offset of panel-b's top-left corner in the combined image
    """
    h, w = img.shape[:2]
    portrait = h > w

    if portrait:
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        profile = gray.mean(axis=1)          # one brightness value per row
        sep     = _find_separator(profile, h)
        if sep is not None:
            a, b = img[:sep], img[sep:]
        else:
            half = h // 2
            a, b = img[:half], img[h - half:]
            print("[INFO] No separator found — falling back to h//2 cut")
            sep = half
    else:
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        profile = gray.mean(axis=0)          # one brightness value per column
        sep     = _find_separator(profile, w)
        if sep is not None:
            a, b = img[:, :sep], img[:, sep:]
        else:
            half = w // 2
            a, b = img[:, :half], img[:, w - half:]
            print("[INFO] No separator found — falling back to w//2 cut")
            sep = half

    # Make sure both halves are the same size (crop the larger to match)
    if portrait:
        min_h   = min(a.shape[0], b.shape[0])
        a_start = sep - min_h   # where panel-a begins in combined-image coords
        b_start = sep           # where panel-b begins in combined-image coords
        a, b    = a[-min_h:], b[:min_h]   # keep bottom of A and top of B
    else:
        min_w   = min(a.shape[1], b.shape[1])
        a_start = sep - min_w
        b_start = sep
        a, b    = a[:, -min_w:], b[:, :min_w]

    print(f"[INFO] Auto-sliced → A{a.shape[:2]}  B{b.shape[:2]}  "
          f"a_start={a_start}  b_start={b_start}")
    return a, b, a_start, b_start


# ─────────────────────────────────────────────────────────────────────────────
#  2.  ALIGNMENT  (3 stages)
# ─────────────────────────────────────────────────────────────────────────────

def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Fast structural similarity on 512x512 thumbnails."""
    ga = _gray(cv2.resize(a, (512, 512)))
    gb = _gray(cv2.resize(b, (512, 512)))
    score, _ = ssim(ga, gb, full=True)
    return float(score)


def _warp_h(src: np.ndarray, H: np.ndarray, wh: tuple) -> np.ndarray:
    """Homography warp with Lanczos + REFLECT_101 border."""
    return cv2.warpPerspective(src, H, wh,
                               flags=cv2.INTER_LANCZOS4,
                               borderMode=cv2.BORDER_REFLECT_101)


def _homography_ok(H: np.ndarray, w: int, h: int) -> bool:
    """Return False if H flips, collapses, or wildly scales the image."""
    if H is None:
        return False
    pts  = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
    out  = cv2.perspectiveTransform(pts, H).reshape(-1,2)
    ow   = float(np.max(out[:,0]) - np.min(out[:,0]))
    oh   = float(np.max(out[:,1]) - np.min(out[:,1]))
    if ow < 1 or oh < 1:
        return False
    sx, sy = ow/w, oh/h
    lo, hi = 1.0/MAX_WARP_SCALE, float(MAX_WARP_SCALE)
    return lo < sx < hi and lo < sy < hi


# ── Stage 1: canvas normalisation ────────────────────────────────────────────

def _stage1_scale(ref: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """Bring tgt to the same canvas size as ref without distorting content."""
    h,  w  = ref.shape[:2]
    ht, wt = tgt.shape[:2]

    if h == ht and w == wt:
        print("[INFO] Stage-1: same size — skip")
        return tgt

    ar_r = w  / h
    ar_t = wt / ht
    diff = abs(ar_r - ar_t) / max(ar_r, ar_t)

    if diff <= SAME_RATIO_TOL:
        out = cv2.resize(tgt, (w, h), interpolation=cv2.INTER_LANCZOS4)
        print(f"[INFO] Stage-1: same ratio ({diff*100:.1f}% diff) → Lanczos resize")
        return out

    # Different ratios: fit inside ref canvas and pad with the median edge colour
    scale   = min(w / wt, h / ht)
    nw, nh  = int(wt * scale), int(ht * scale)
    resized = cv2.resize(tgt, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    edge    = np.concatenate([resized[0].reshape(-1,3), resized[-1].reshape(-1,3),
                              resized[:,0].reshape(-1,3), resized[:,-1].reshape(-1,3)])
    pad_c   = tuple(int(x) for x in np.median(edge, axis=0))
    canvas  = np.full((h, w, 3), pad_c, dtype=np.uint8)
    y0, x0  = (h - nh) // 2, (w - nw) // 2
    canvas[y0:y0+nh, x0:x0+nw] = resized
    print(f"[INFO] Stage-1: different ratio → fit-and-pad  (scale={scale:.3f})")
    return canvas


# ── Stage 2: SIFT / AKAZE / ORB feature alignment ───────────────────────────

def _match(g_ref, g_tgt, name: str):
    """Detect & match keypoints; return (kp_ref, kp_tgt, good_matches)."""
    if   name == "SIFT":  det, norm = cv2.SIFT_create(nfeatures=12000), cv2.NORM_L2
    elif name == "AKAZE": det, norm = cv2.AKAZE_create(),                cv2.NORM_HAMMING
    else:                 det, norm = cv2.ORB_create(nfeatures=12000),   cv2.NORM_HAMMING

    kp1, d1 = det.detectAndCompute(g_ref, None)
    kp2, d2 = det.detectAndCompute(g_tgt, None)
    if d1 is None or d2 is None or len(kp1) < 8 or len(kp2) < 8:
        return kp1, kp2, []

    matcher = cv2.BFMatcher(norm, crossCheck=False)
    raw     = matcher.knnMatch(d2, d1, k=2)
    good    = [m for m,n in raw if len((m,n))==2 and m.distance < 0.78*n.distance]
    return kp1, kp2, good


def _stage2_features(ref: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """SIFT → AKAZE → ORB chain. Returns warped tgt, or tgt unchanged on failure."""
    h, w  = ref.shape[:2]
    g_ref = _gray(ref)
    g_tgt = _gray(tgt)

    for name in ("SIFT", "AKAZE", "ORB"):
        kp1, kp2, good = _match(g_ref, g_tgt, name)
        print(f"[INFO] Stage-2 {name}: {len(good)} good matches")
        if len(good) < 12:
            continue

        src = np.float32([kp2[m.queryIdx].pt for m in good]).reshape(-1,1,2)
        dst = np.float32([kp1[m.trainIdx].pt for m in good]).reshape(-1,1,2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)

        if not _homography_ok(H, w, h):
            print(f"[WARN] Stage-2 {name}: homography failed sanity check")
            continue

        inliers = int(mask.sum()) if mask is not None else 0
        print(f"[INFO] Stage-2 {name}: accepted  ({inliers} inliers)")
        return _warp_h(tgt, H, (w, h))

    print("[WARN] Stage-2: no detector produced a usable homography")
    return tgt


# ── Stage 3: ECC sub-pixel refinement ────────────────────────────────────────

def _stage3_ecc(ref: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """ECC on a thumbnail, scaled back to full resolution. Returns tgt on failure."""
    h, w   = ref.shape[:2]
    sc     = min(1.0, ECC_MAX_DIM / max(h, w))
    sw, sh = int(w*sc), int(h*sc)

    g_ref  = _gray(cv2.resize(ref, (sw, sh)))
    g_tgt  = _gray(cv2.resize(tgt, (sw, sh)))

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, ECC_MAX_ITER, ECC_EPS)
    H_init   = np.eye(3, dtype=np.float32)
    try:
        _, H_small = cv2.findTransformECC(g_ref, g_tgt, H_init,
                                          cv2.MOTION_HOMOGRAPHY, criteria,
                                          inputMask=None, gaussFiltSize=5)
    except cv2.error as e:
        print(f"[WARN] Stage-3 ECC: {e}")
        return tgt

    H_full       = H_small.copy()
    H_full[0, 2] /= sc   # scale tx back up
    H_full[1, 2] /= sc   # scale ty back up

    if not _homography_ok(H_full, w, h):
        print("[WARN] Stage-3 ECC: result is insane — skipped")
        return tgt

    return _warp_h(tgt, H_full, (w, h))


# ── Master align ─────────────────────────────────────────────────────────────

def align(ref: np.ndarray, tgt: np.ndarray, skip_ecc: bool = True) -> np.ndarray:
    """
    Run 3-stage alignment.  Each stage is only committed if it strictly
    improves SSIM (or at most degrades it by 0.005 in Stage-2).
    """
    s0 = _ssim(ref, tgt)
    print(f"[INFO] SSIM before alignment : {s0:.4f}")

    # Stage 1 always applies (just normalises canvas)
    tgt = _stage1_scale(ref, tgt)
    s1  = _ssim(ref, tgt)
    print(f"[INFO] SSIM after  Stage-1   : {s1:.4f}")

    # Stage 2: keep if not worse than Stage-1 by more than 0.5%
    tgt2 = _stage2_features(ref, tgt)
    s2   = _ssim(ref, tgt2)
    if s2 >= s1 - 0.005:
        tgt, s_cur = tgt2, s2
    else:
        s_cur = s1
        print("[INFO] Stage-2 made things worse — reverted")
    print(f"[INFO] SSIM after  Stage-2   : {s_cur:.4f}")

    # Stage 3: keep only if strictly better by at least 0.1%
    if not skip_ecc:
        tgt3 = _stage3_ecc(ref, tgt)
        s3   = _ssim(ref, tgt3)
        if s3 > s_cur + 0.001:
            tgt, s_cur = tgt3, s3
            print(f"[INFO] SSIM after  Stage-3   : {s_cur:.4f}  (ECC applied)")
        else:
            print(f"[INFO] SSIM after  Stage-3   : {s3:.4f}  (ECC skipped — no improvement)")

    return tgt


# ─────────────────────────────────────────────────────────────────────────────
#  3.  DIFFERENCE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _auto_threshold(deltas: list, floor: float):
    """
    Find the natural noise/signal boundary in a list of colour-delta scores.

    Key insight: the gap filter exists ONLY to separate warp/JPEG noise
    (low-delta contours) from real puzzle differences (high-delta contours).
    If every candidate is already above the floor, there IS no noise cluster
    — keep everything.

    A gap is accepted as a noise/signal cut only when:
      • At least one candidate sits BELOW the floor  (there is actual noise)
      • The gap is >= 2x the second-largest gap       (relative dominance)
      • The gap's absolute size is > 20               (not just scaled-up noise)
      • It leaves >= 1 value on each side
    """
    if len(deltas) < 3:
        return floor, "too few candidates — using floor"

    s = sorted(deltas)

    # ── Fast path: no noise present ──────────────────────────────────────────
    # If the smallest delta is already above the floor, all candidates are real.
    if s[0] >= floor:
        return floor, f"all deltas above floor {floor:.1f} — keeping all {len(s)} candidates"

    gaps = [s[i+1] - s[i] for i in range(len(s)-1)]
    top2 = sorted(gaps, reverse=True)[:2]
    idx  = int(np.argmax(gaps))
    nc   = idx + 1           # noise count (below cut)
    sc   = len(s) - nc       # signal count (above cut)

    dominant = (
        top2[0] > 20.0
        and (len(top2) < 2 or top2[0] >= 2.0 * top2[1])
        and nc >= 1
        and sc >= 1
    )

    if dominant:
        t      = (s[idx] + s[idx+1]) / 2.0
        reason = f"dominant gap {s[idx]:.1f}→{s[idx+1]:.1f}, dropping {nc} noise contour(s)"
        return t, reason

    return floor, f"no dominant gap — keeping all above floor {floor:.1f}"


def _lab_delta_map(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Per-pixel CIE-Lab Euclidean distance (ΔE), scaled to 0-255.

    Why this matters: SSIM operates on greyscale luminance and completely
    ignores hue/saturation changes.  A red object swapped for a green one
    at the same brightness will score near-zero on SSIM but very high here.
    Fusing both maps catches every category of difference.
    """
    la    = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).astype(np.float32)
    lb    = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    delta = np.sqrt(np.sum((la - lb) ** 2, axis=2))
    mx    = delta.max()
    return (delta / mx * 255).astype(np.uint8) if mx > 0 else delta.astype(np.uint8)


def detect(img_a: np.ndarray,
           img_b: np.ndarray,
           min_area:    int   = 50,
           delta_floor: float = 8.0):
    """
    Detect all real differences between two aligned images.

    Returns
    -------
    circles : list of (cx, cy, radius) in img_a coordinate space
    count   : number of differences found
    """
    h, w  = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # ── SSIM structural difference map ───────────────────────────────────────
    score, diff = ssim(_gray(img_a), _gray(img_b), full=True)
    print(f"[INFO] SSIM for detection    : {score:.4f}")

    diff_u8  = (diff * 255).clip(0, 255).astype(np.uint8)
    inv      = cv2.bitwise_not(diff_u8)

    # ── CIE-Lab colour difference map ────────────────────────────────────────
    # Catches colour-only swaps that SSIM misses (same luminance, different hue).
    lab_diff = _lab_delta_map(img_a, img_b)

    # ── Fuse: take pixel-wise maximum of both maps ────────────────────────────
    # Any region that differs structurally OR in colour will be flagged.
    fused = np.maximum(inv, lab_diff)

    _, thresh = cv2.threshold(fused, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Morphological cleanup: merge nearby fragments, kill isolated specks
    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9,9))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k9)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k5)

    # Border mask: kills arc/frame artifact from warpPerspective edge fill
    border = max(10, int(min(h, w) * 0.04))
    bmask  = np.zeros_like(thresh)
    bmask[border:h-border, border:w-border] = 255
    thresh = cv2.bitwise_and(thresh, bmask)

    # ── Contours + colour-delta scoring ───────────────────────────────────────
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cdiff       = np.mean(cv2.absdiff(img_a, img_b).astype(np.float32), axis=2)

    candidates = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        m = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(m, [cnt], -1, 255, cv2.FILLED)
        delta = cv2.mean(cdiff, mask=m)[0]
        candidates.append((cnt, delta))

    if not candidates:
        print("[WARN] No candidates survived filtering.")
        return [], 0

    deltas = sorted(d for _, d in candidates)
    print(f"[INFO] Candidates : {len(candidates)}  "
          f"deltas: {[round(d,1) for d in deltas]}")

    threshold, reason = _auto_threshold(deltas, delta_floor)
    print(f"[INFO] Δ-threshold : {threshold:.1f}  ({reason})")

    # ── Merge nearby contours, then build one circle per group ────────────────
    #
    # SSIM often splits a single visual difference (e.g. one added animal) into
    # several nearby contour fragments.  Drawing a separate circle per fragment
    # inflates the count and produces circles that only cover part of the
    # difference region.
    #
    # Fix: group contours whose centres lie within MERGE_RADIUS of any already-
    # grouped contour.  Pool all contour points in the group together and fit
    # one minimum-enclosing circle around the union — so the circle always
    # covers the whole difference, not just one fragment of it.
    #
    MERGE_RADIUS = 80   # px — tune up for larger puzzles if needed

    surviving = [(cnt, delta) for cnt, delta in candidates if delta >= threshold]

    # Each group entry: [sub_circles [(cx,cy,r),...], max_delta, centre_x, centre_y]
    groups: list = []
    for cnt, delta in surviving:
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        cx, cy, r = float(cx), float(cy), float(r)
        merged = False
        for grp in groups:
            gcx, gcy = grp[2], grp[3]
            if ((cx - gcx) ** 2 + (cy - gcy) ** 2) ** 0.5 < MERGE_RADIUS:
                grp[0].append((cx, cy, r))
                grp[1] = max(grp[1], delta)
                grp[2] = float(np.mean([s[0] for s in grp[0]]))
                grp[3] = float(np.mean([s[1] for s in grp[0]]))
                merged = True
                break
        if not merged:
            groups.append([[(cx, cy, r)], delta, cx, cy])

    print(f"[INFO] After merging: {len(groups)} groups  (was {len(surviving)} contours)")

    circles = []
    for grp in groups:
        sub = grp[0]
        centres = np.array([[s[0], s[1]] for s in sub], dtype=np.float32)
        max_sub_r = max(s[2] for s in sub)
        if len(centres) == 1:
            cx, cy = centres[0]
            r = max(int(max_sub_r) + 12, 18)
        else:
            (cx, cy), span = cv2.minEnclosingCircle(centres.reshape(-1, 1, 2))
            r = max(int(span + max_sub_r) + 12, 18)
        circles.append((int(cx), int(cy), r))

    return circles, len(groups)


# ─────────────────────────────────────────────────────────────────────────────
#  3b.  DETECTION — LINE-DRAWING MODE
# ─────────────────────────────────────────────────────────────────────────────

# Auto-detect: mean HSV saturation below this → treat as B&W line drawing
_SATURATION_LINE_THRESHOLD = 20

def is_line_drawing(img: np.ndarray) -> bool:
    """Return True if image is a B&W / greyscale line drawing (low saturation)."""
    hsv      = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mean_sat = float(hsv[:, :, 1].mean())
    mode     = "line-drawing" if mean_sat < _SATURATION_LINE_THRESHOLD else "colour"
    print(f"[INFO] Mean saturation: {mean_sat:.1f}  → {mode} mode")
    return mean_sat < _SATURATION_LINE_THRESHOLD


def detect_line(img_a: np.ndarray, img_b: np.ndarray) -> tuple:
    """
    Detection pipeline tuned for B&W line-drawing puzzles.

    Key insight — max_diff_min filter:
      SIFT warp residuals are smooth, low-amplitude blurs; their peak pixel
      difference sits around 80–120.  Real ink-line differences are sharp and
      always peak at 200+.  Threshold at 160 cleanly separates the two.

    Other differences from colour mode:
      • Fixed SSIM threshold (30) instead of Otsu — Otsu merges adjacent small
        line-diffs into one big blob.
      • Tiny morph kernel (3px) — don't bridge small but distinct differences.
      • NMS (non-maximum suppression, 80px) — merges overlapping circles.
      • delta_floor=5 — ink changes are subtle in greyscale.

    Returns
    -------
    circles : list of (cx, cy, radius)
    count   : number of differences found
    """
    LINE_SSIM_THRESH  = 30
    LINE_MORPH_KSIZE  = 3
    LINE_MIN_AREA     = 20
    LINE_DELTA_FLOOR  = 5.0
    # LINE_MAX_DIFF_MIN: JPEG compression on small images soft-clips peaks.
    # Scale with image size: larger=sharper peaks, smaller=softer.
    LINE_MAX_DIFF_MIN = max(80, int(min(img_a.shape[:2]) * 0.45))
    # LINE_NMS_RADIUS: 80px on a 233px panel = 34% of image — way too big.
    # Scale to ~12% of the shorter panel edge.
    LINE_NMS_RADIUS = max(20, int(min(img_a.shape[:2]) * 0.12))

    h, w  = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)

    score, diff = ssim(_gray(img_a), _gray(img_b), full=True)
    print(f"[INFO] SSIM for detection    : {score:.4f}")

    inv      = cv2.bitwise_not((diff * 255).clip(0, 255).astype(np.uint8))
    _, thresh = cv2.threshold(inv, LINE_SSIM_THRESH, 255, cv2.THRESH_BINARY)

    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                  (LINE_MORPH_KSIZE, LINE_MORPH_KSIZE))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k)

    border = max(10, int(min(h, w) * 0.04))
    bmask  = np.zeros_like(thresh)
    bmask[border:h - border, border:w - border] = 255
    thresh = cv2.bitwise_and(thresh, bmask)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cdiff = np.mean(cv2.absdiff(img_a, img_b).astype(np.float32), axis=2)
    ga    = _gray(img_a).astype(np.float64)
    gb    = _gray(img_b).astype(np.float64)

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
        cx, cy, r   = int(cx), int(cy), int(r)

        # Peak-diff filter: warp residuals are blurry → low peak, real diffs are sharp
        x1 = max(0, cx - r - 5);  y1 = max(0, cy - r - 5)
        x2 = min(w, cx + r + 5);  y2 = min(h, cy + r + 5)
        peak = float(np.abs(ga[y1:y2, x1:x2] - gb[y1:y2, x1:x2]).max())
        if peak < LINE_MAX_DIFF_MIN:
            print(f"       skip ({cx:4d},{cy:4d}) peak={peak:.0f} < {LINE_MAX_DIFF_MIN}  (warp artifact)")
            continue

        # Cap radius: individual line-drawing differences are small features.
        # A contour enclosing a large alignment-residual blob would otherwise
        # produce a circle spanning half the image.  15% of the shorter panel
        # edge is enough to comfortably surround any real single difference.
        max_r = int(min(h, w) * 0.15)
        candidates.append((cx, cy, min(max(r + 15, 20), max_r), delta))

    print(f"[INFO] Candidates after peak-diff filter: {len(candidates)}")

    # Non-maximum suppression — collapse circles whose centres are close
    candidates.sort(key=lambda x: -x[3])    # highest delta first
    kept = []
    for cx, cy, r, d in candidates:
        if not any(((cx-kx)**2 + (cy-ky)**2)**0.5 < LINE_NMS_RADIUS
                   for kx, ky, _, _ in kept):
            kept.append((cx, cy, r, d))

    print(f"[INFO] After NMS: {len(kept)} circles")

    circles = [(cx, cy, r) for cx, cy, r, _ in kept]
    return circles, len(kept)


# ─────────────────────────────────────────────────────────────────────────────
#  4.  OUTPUT — colour, badges, Khmer caption
# ─────────────────────────────────────────────────────────────────────────────

def random_run_color() -> tuple:
    """
    Pick ONE random vivid colour for this entire run.
    Generated in HSV space: saturation ≥ 0.80, value ≥ 0.80.
    Guarantees the result is never black, white, or grey.
    Returns (R, G, B).
    """
    h = random.uniform(0, 360)
    s = random.uniform(0.80, 1.00)
    v = random.uniform(0.80, 1.00)
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x),
               (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def _load_font(path, size):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_circles_on_panel(panel_pil: Image.Image,
                           circles:   list,
                           color:     tuple) -> Image.Image:
    """
    Draw one perfect circle + numbered badge per difference onto panel_pil.
    Coordinates must be in panel_pil's own pixel space (no offset needed).
    Returns a new annotated copy.
    """
    img   = panel_pil.copy()
    draw  = ImageDraw.Draw(img)
    bfont = _load_font(_LATIN_FONT, 24)

    for idx, (cx, cy, r) in enumerate(circles):
        # Plain coloured ring — no white halo, clean look
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=4)

        # Numbered badge: filled disc + white number
        br    = 15
        bx    = cx + int(r * 0.70)
        by    = cy - int(r * 0.70)
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=color)
        label = str(idx + 1)
        bb    = draw.textbbox((0, 0), label, font=bfont)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((bx - tw // 2 - bb[0], by - th // 2 - bb[1]),
                  label, font=bfont, fill=(255, 255, 255))

    return img


def _khmer_digits(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩"))


def make_khmer_banner(width: int, count: int) -> Image.Image:
    """Dark banner with gold Khmer text: 'Found X differences'."""
    BH    = 80
    text  = f"រកឃើញភាពខុសគ្នា {_khmer_digits(count)} កន្លែង"
    banner = Image.new("RGB", (width, BH), (30, 30, 50))
    draw   = ImageDraw.Draw(banner)
    kfont, kfont_path = pick_random_khmer_font(40)
    print(f"[INFO] Khmer banner font : {os.path.basename(kfont_path)}")
    bb     = draw.textbbox((0, 0), text, font=kfont)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx     = (width - tw) // 2 - bb[0]
    ty     = (BH    - th) // 2 - bb[1]
    draw.text((tx + 2, ty + 2), text, font=kfont, fill=(10, 10, 20))   # shadow
    draw.text((tx,     ty    ), text, font=kfont, fill=(255, 215, 60))  # gold
    return banner


# ─────────────────────────────────────────────────────────────────────────────
#  5.  OUTPUT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────


def add_watermark(img: Image.Image) -> Image.Image:
    """
    Stamp a semi-transparent diagonal Khmer watermark across the image.
    Text: ចម្លើយពីក្មួយ និរន្ត  ("Answer from Nephew Nirant")
    """
    text  = "ចម្លើយពីក្មួយ និរន្ត"
    w, h  = img.size

    # Build the watermark on a transparent canvas the same size as the image
    wm    = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(wm)

    # Pick font size proportional to image width
    font_size = max(24, w // 18)
    font, _ = pick_random_khmer_font(font_size)

    bb   = draw.textbbox((0, 0), text, font=font)
    tw   = bb[2] - bb[0]
    th   = bb[3] - bb[1]

    # Tile the text diagonally across the whole image
    step_x = int(tw * 1.6)
    step_y = int(th * 3.5)
    angle  = -30

    for row, y0 in enumerate(range(-th * 2, h + th * 2, step_y)):
        x_shift = (row % 2) * (step_x // 2)          # stagger every other row
        for x0 in range(-tw - x_shift, w + tw, step_x):
            # Render each instance of the text onto a tiny tile, then rotate and paste
            tile = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(tile)
            # White outline for legibility on any background
            for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                tdraw.text((10 - bb[0] + dx, 10 - bb[1] + dy),
                           text, font=font, fill=(255, 255, 255, 60))
            tdraw.text((10 - bb[0], 10 - bb[1]),
                       text, font=font, fill=(180, 180, 180, 55))
            rotated = tile.rotate(angle, expand=True)
            wm.paste(rotated, (x0, y0), rotated)

    # Composite watermark over original
    out = img.convert("RGBA")
    out = Image.alpha_composite(out, wm)
    return out.convert("RGB")


def build_stacked_output(combined_bgr:  np.ndarray,
                          img_a:         np.ndarray,
                          img_b_aligned: np.ndarray,
                          circles:       list,
                          a_start:       int,
                          b_start:       int,
                          color:         tuple,
                          count:         int) -> Image.Image:
    """
    Reconstruct the original stacked combined image with annotated panels.

    WHY WE ANNOTATE PANELS SEPARATELY:
      Circles live in img_a coordinate space.  img_b_aligned was warped to
      match img_a, so the same (cx, cy) positions are valid on img_b_aligned.
      If we instead tried to draw circles into the ORIGINAL combined image at
      (cx, cy + b_start), the bottom panel circles would be wrong — the original
      img_b was never warped, so its content is shifted relative to img_a.

      Solution: annotate each panel in its own coordinate space, then paste at
      the correct offset.  Circles are guaranteed to land on the right pixels.
    """
    BH = 80
    oh, ow = combined_bgr.shape[:2]

    pil_a = Image.fromarray(cv2.cvtColor(img_a,         cv2.COLOR_BGR2RGB))
    pil_b = Image.fromarray(cv2.cvtColor(img_b_aligned, cv2.COLOR_BGR2RGB))
    pil_a = draw_circles_on_panel(pil_a, circles, color)
    pil_b = draw_circles_on_panel(pil_b, circles, color)

    # Start from the original combined image — preserves headers, borders, etc.
    base   = Image.fromarray(cv2.cvtColor(combined_bgr, cv2.COLOR_BGR2RGB))
    canvas = Image.new("RGB", (ow, BH + oh), (30, 30, 50))
    canvas.paste(base,  (0, BH))
    canvas.paste(pil_a, (0, BH + a_start))   # overwrite top panel
    canvas.paste(pil_b, (0, BH + b_start))   # overwrite bottom panel (aligned)
    canvas.paste(make_khmer_banner(ow, count), (0, 0))
    return canvas


def build_sidebyside_output(img_a:         np.ndarray,
                             img_b_aligned: np.ndarray,
                             circles:       list,
                             color:         tuple,
                             count:         int) -> Image.Image:
    """Two separate images: annotate both panels and place side by side."""
    BH, GAP = 80, 6
    h, w    = img_a.shape[:2]

    pil_a = Image.fromarray(cv2.cvtColor(img_a,         cv2.COLOR_BGR2RGB))
    pil_b = Image.fromarray(cv2.cvtColor(img_b_aligned, cv2.COLOR_BGR2RGB))
    pil_a = draw_circles_on_panel(pil_a, circles, color)
    pil_b = draw_circles_on_panel(pil_b, circles, color)

    total_w = w * 2 + GAP
    canvas  = Image.new("RGB", (total_w, BH + h), (30, 30, 50))
    canvas.paste(pil_a, (0,       BH))
    canvas.paste(pil_b, (w + GAP, BH))
    ImageDraw.Draw(canvas).rectangle([w, BH, w + GAP, BH + h], fill=(180, 180, 180))
    canvas.paste(make_khmer_banner(total_w, count), (0, 0))
    return canvas


# ─────────────────────────────────────────────────────────────────────────────
#  6.  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Automatic spot-the-difference detector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py original.png modified.png
  python spot_the_difference.py puzzle.jpg --output marked.png
  python spot_the_difference.py puzzle.jpg --ecc             (enable ECC refinement, slower)
  python spot_the_difference.py puzzle.jpg --no-align    (already aligned)
        """,
    )
    p.add_argument("images",  nargs="+", metavar="IMAGE",
                   help="One combined image OR two separate images.")
    p.add_argument("--output",      default="circled_result.png",
                   help="Output filename  (default: circled_result.png)")
    p.add_argument("--min-area",    type=int,   default=50,
                   help="Minimum contour area in px  (default: 50)")
    p.add_argument("--delta-floor", type=float, default=8.0,
                   help="Colour-delta noise floor  (default: 8)")
    p.add_argument("--mode",        choices=["auto","colour","line"], default="auto",
                   help="Detection mode: auto (default), colour, or line")
    p.add_argument("--no-align",    action="store_true",
                   help="Skip all alignment")
    p.add_argument("--ecc",          action="store_true",
                   help="Enable ECC sub-pixel refinement (slower, rarely needed)")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
#  7.  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if len(args.images) == 1:
        print(f"[INFO] Single image → auto-slicing: {args.images[0]!r}")
        combined = load_bgr(args.images[0])
        img_a, img_b, a_start, b_start = auto_slice(combined)
        two_image_mode = False
    elif len(args.images) == 2:
        print(f"[INFO] Two images: {args.images[0]!r}  vs  {args.images[1]!r}")
        combined       = None
        a_start        = b_start = 0
        img_a          = load_bgr(args.images[0])
        img_b          = load_bgr(args.images[1])
        two_image_mode = True
    else:
        sys.exit("[ERROR] Provide 1 combined image or 2 separate images.")

    print(f"[INFO] A: {img_a.shape[:2]}   B: {img_b.shape[:2]}")

    if args.no_align:
        img_b_aligned = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]),
                                   interpolation=cv2.INTER_LANCZOS4)
        print("[INFO] Alignment skipped (--no-align)")
    else:
        img_b_aligned = align(img_a, img_b, skip_ecc=not args.ecc)

    # Mode selection
    if args.mode == "auto":
        line_mode = is_line_drawing(img_a)
    else:
        line_mode = (args.mode == "line")
        print(f"[INFO] Mode forced: {'line-drawing' if line_mode else 'colour'}")

    if line_mode:
        circles, count = detect_line(img_a, img_b_aligned)
    else:
        circles, count = detect(img_a, img_b_aligned,
                                min_area=args.min_area,
                                delta_floor=args.delta_floor)

    # One random vivid colour for all circles this run
    color = random_run_color()
    print(f"[INFO] Run colour : RGB{color}")

    # Build and save output
    if two_image_mode:
        result = build_sidebyside_output(img_a, img_b_aligned, circles, color, count)
    else:
        result = build_stacked_output(combined, img_a, img_b_aligned,
                                      circles, a_start, b_start, color, count)

    result = add_watermark(result)
    result.save(args.output, quality=95)

    print()
    print("=" * 45)
    print(f"  Mode              : {'line-drawing' if line_mode else 'colour'}")
    print(f"  Differences found : {count}")
    print(f"  Run colour        : RGB{color}")
    print(f"  Saved to          : {args.output!r}")
    print("=" * 45)


if __name__ == "__main__":
    main()