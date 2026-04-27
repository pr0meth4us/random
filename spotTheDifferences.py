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
  SSIM difference map → Otsu threshold → morphological cleanup
  → border mask → contour detection → colour-delta scoring
  → auto gap-threshold → contour grouping/merging → red circles on output

Usage:
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py original.png modified.png
  python spot_the_difference.py puzzle.jpg --output result.png

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

MAX_WARP_SCALE = 3.0   # reject homography if any axis scales by more than this
SAME_RATIO_TOL = 0.03  # treat aspect ratios within 3% as "same"
ECC_MAX_DIM    = 400   # ECC runs on a thumbnail — smaller = faster
ECC_MAX_ITER   = 150   # usually converges in <50 iters if it's going to work
ECC_EPS        = 1e-5


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
    # (i.e. there actually IS a lighter gap between two content regions)
    if local_max - local_mean < 15:
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

    # Make sure both halves are the same size (crop the larger to match)
    if portrait:
        min_h = min(a.shape[0], b.shape[0])
        a, b  = a[-min_h:], b[:min_h]       # keep bottom of A and top of B
    else:
        min_w = min(a.shape[1], b.shape[1])
        a, b  = a[:, -min_w:], b[:, :min_w]

    print(f"[INFO] Auto-sliced → A{a.shape[:2]}  B{b.shape[:2]}")
    return a, b


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


def detect(img_a: np.ndarray,
           img_b: np.ndarray,
           min_area:    int   = 50,
           delta_floor: float = 8.0):
    """Detect and circle all real differences between two aligned images."""
    h, w  = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)

    # ── SSIM difference map ───────────────────────────────────────────────────
    score, diff = ssim(_gray(img_a), _gray(img_b), full=True)
    print(f"[INFO] SSIM for detection    : {score:.4f}")

    diff_u8  = (diff * 255).clip(0, 255).astype(np.uint8)
    inv      = cv2.bitwise_not(diff_u8)
    _, thresh = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

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
        return img_b.copy(), 0

    deltas = sorted(d for _, d in candidates)
    print(f"[INFO] Candidates : {len(candidates)}  "
          f"deltas: {[round(d,1) for d in deltas]}")

    threshold, reason = _auto_threshold(deltas, delta_floor)
    print(f"[INFO] Δ-threshold : {threshold:.1f}  ({reason})")

    # ── Merge nearby contours, then draw one circle per group ─────────────────
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
    #
    # Store per-contour (centre, radius) rather than raw points.
    # When drawing, we fit a circle around sub-circle centres then expand by
    # the largest sub-radius — tight enough to cover every fragment without
    # being inflated by individual distant edge points on large contours.
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

    result = img_b.copy()
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
        cv2.circle(result, (int(cx), int(cy)), r, (0, 0, 255), 3)

    return result, len(groups)


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
    """
    LINE_SSIM_THRESH  = 30
    LINE_MORPH_KSIZE  = 3
    LINE_MIN_AREA     = 20
    LINE_DELTA_FLOOR  = 5.0
    LINE_MAX_DIFF_MIN = 160   # reject anything whose peak diff is below this
    LINE_NMS_RADIUS   = 80    # merge circles whose centres are within this px

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

        candidates.append((cx, cy, max(r + 15, 20), delta))

    print(f"[INFO] Candidates after peak-diff filter: {len(candidates)}")

    # Non-maximum suppression — collapse circles whose centres are close
    candidates.sort(key=lambda x: -x[3])    # highest delta first
    kept = []
    for cx, cy, r, d in candidates:
        if not any(((cx-kx)**2 + (cy-ky)**2)**0.5 < LINE_NMS_RADIUS
                   for kx, ky, _, _ in kept):
            kept.append((cx, cy, r, d))

    print(f"[INFO] After NMS: {len(kept)} circles")

    result = img_b.copy()
    for cx, cy, r, _ in kept:
        cv2.circle(result, (cx, cy), r, (0, 0, 255), 2)

    return result, len(kept)


# ─────────────────────────────────────────────────────────────────────────────
#  4.  CLI
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
#  5.  MAIN
# ─────────────────────────────────────────────────────────────────────────────

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
        img_b = align(img_a, img_b, skip_ecc=not args.ecc)

    # Mode selection
    if args.mode == "auto":
        line_mode = is_line_drawing(img_a)
    else:
        line_mode = (args.mode == "line")
        print(f"[INFO] Mode forced: {'line-drawing' if line_mode else 'colour'}")

    if line_mode:
        result, count = detect_line(img_a, img_b)
    else:
        result, count = detect(img_a, img_b,
                               min_area=args.min_area,
                               delta_floor=args.delta_floor)

    cv2.imwrite(args.output, result)

    print()
    print("=" * 45)
    print(f"  Mode              : {'line-drawing' if line_mode else 'colour'}")
    print(f"  Differences found : {count}")
    print(f"  Saved to          : {args.output!r}")
    print("=" * 45)


if __name__ == "__main__":
    main()