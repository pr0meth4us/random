#!/usr/bin/env python3
"""
spot_the_difference.py  (v2 – fixed)
=====================================
Fixes over v1:
  FIX A — Large blobs (r > max_allowed_r) are now SPLIT via distance-transform
           watershed instead of silently dropped.  This recovers the tail and
           cushion-stripe differences that were being swallowed by one giant
           alignment-artifact blob.
  FIX B — HUE_DILATE_KSIZE reduced 21→9 so the hue mask doesn't bleed and
           fuse unrelated regions into one oversized blob.
  FIX C — MERGE_RADIUS reduced 88→55 so spatially-separate differences
           (tail vs. cushion-stripe) don't collapse into a single circle that
           then exceeds the radius cap and gets dropped.
  FIX D — delta_floor lowered 8.0→7.0 to catch low-contrast diffs like the tail.
  FIX E — Circle padding tightened (+12→+6) so circles hug the real diff region.
  FIX F — No per-circle numbering badges.  Only the total count is shown on the
           Khmer banner.

Usage (unchanged):
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py original.png modified.png
  python spot_the_difference.py numbergrid.png --mode number
"""

import sys
import argparse
import warnings
import random
import os
import re
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
#  TUNING CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MAX_WARP_SCALE       = 3.0
SAME_RATIO_TOL       = 0.03
ECC_MAX_DIM          = 400
ECC_MAX_ITER         = 150
ECC_EPS              = 1e-5

NUM_CELL_PAD         = 4
NUM_MIN_COLS         = 3
NUM_MIN_ROWS         = 3

HUE_FIXED_THRESH     = 30    # degrees — hue arc above this fires
HUE_SAT_MIN          = 30    # ignore pixels below this saturation
HUE_DILATE_KSIZE     = 9     # FIX B: was 21 — smaller kernel prevents blob fusion
HUE_SCORE_WEIGHT     = 0.5
MAX_BLOB_RADIUS_FRAC = 0.25
MERGE_RADIUS         = 55    # FIX C: was 88 — tighter merging
LOW_DELTA_FRAC       = 0.40
CIRCLE_PAD           = 6     # FIX E: was 12 — tighter circles


# ─────────────────────────────────────────────────────────────────────────────
#  FONTS
# ─────────────────────────────────────────────────────────────────────────────

_KHMER_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerifKhmer-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerifKhmer-Regular.ttf",
    "C:/Windows/Fonts/NotoSansKhmer-Bold.ttf",
    "C:/Windows/Fonts/NotoSansKhmer-Regular.ttf",
    "C:/Windows/Fonts/NotoSerifKhmer-Bold.ttf",
    "C:/Windows/Fonts/NotoSerifKhmer-Regular.ttf",
    "/Library/Fonts/NotoSansKhmer-Bold.ttf",
    "/Library/Fonts/NotoSansKhmer-Regular.ttf",
    os.path.expanduser("~/Library/Fonts/NotoSansKhmer-Bold.ttf"),
    "/usr/local/share/fonts/NotoSansKhmer-Bold.ttf",
    os.path.expanduser("~/.fonts/NotoSansKhmer-Bold.ttf"),
    os.path.expanduser("~/.local/share/fonts/NotoSansKhmer-Bold.ttf"),
]

_AVAILABLE_KHMER_FONTS = [p for p in _KHMER_FONT_CANDIDATES if os.path.exists(p)]

if not _AVAILABLE_KHMER_FONTS:
    print(
        "[WARN] No Khmer fonts found. Khmer text will fall back to the default font.\n"
        "       Linux : sudo apt install fonts-noto-core\n"
        "       macOS : brew install font-noto-sans-khmer"
    )

_LATIN_FONT = next((p for p in [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
] if os.path.exists(p)), None)


def pick_random_khmer_font(size: int):
    import PIL.Image as _PILImg, PIL.ImageDraw as _PILDraw
    test_text = "រកឃើញភាពខុសគ្នា ០១២៣៤៥៦៧៨៩ កន្លែង ចម្លើយពីក្មួយ និរន្ត"
    candidates = list(_AVAILABLE_KHMER_FONTS)
    random.shuffle(candidates)
    for path in candidates:
        try:
            f  = ImageFont.truetype(path, size)
            _d = _PILDraw.Draw(_PILImg.new("RGB", (800, 100)))
            _d.textbbox((0, 0), test_text, font=f)
            _d.text((0, 0), test_text, font=f, fill=(0, 0, 0))
            return f, path
        except Exception:
            continue
    return ImageFont.load_default(), "default"


# ─────────────────────────────────────────────────────────────────────────────
#  1.  IMAGE I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_bgr(path: str) -> np.ndarray:
    return cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)


def _find_separator(profile: np.ndarray, axis_len: int):
    lo = int(axis_len * 0.15)
    hi = int(axis_len * 0.85)
    MIN_PANEL_FRAC = 0.25
    WHITE_THRESH   = 245

    white_bands = []
    in_band = False
    band_start = 0
    for y in range(lo, hi):
        is_white = profile[y] >= WHITE_THRESH
        if is_white and not in_band:
            in_band = True; band_start = y
        elif not is_white and in_band:
            in_band = False
            band_centre = (band_start + y) // 2
            band_max    = float(profile[band_start:y].max())
            top_frac = band_centre / axis_len
            bot_frac = (axis_len - band_centre) / axis_len
            if top_frac >= MIN_PANEL_FRAC and bot_frac >= MIN_PANEL_FRAC:
                white_bands.append((band_centre, band_max))
    if in_band:
        band_centre = (band_start + hi) // 2
        band_max    = float(profile[band_start:hi].max())
        if (band_centre / axis_len >= MIN_PANEL_FRAC and
                (axis_len - band_centre) / axis_len >= MIN_PANEL_FRAC):
            white_bands.append((band_centre, band_max))

    if white_bands:
        mid = axis_len // 2
        sep, bmax = min(white_bands, key=lambda x: abs(x[0] - mid))
        print(f"[INFO] Separator (white-row): y={sep}  brightness={bmax:.0f}")
        return sep

    smoothed   = np.convolve(profile, np.ones(60) / 60, mode='same')
    region     = smoothed[lo:hi]
    local_max  = float(region.max())
    local_mean = float(region.mean())

    if local_max - local_mean < 5:
        return None

    candidates = []
    for i, val in enumerate(region):
        y = lo + i
        if val > local_mean + 5:
            top_frac = y / axis_len
            bot_frac = (axis_len - y) / axis_len
            balanced = (top_frac >= MIN_PANEL_FRAC and bot_frac >= MIN_PANEL_FRAC)
            candidates.append((val, y, balanced))

    balanced_cands   = [(v, y) for v, y, ok in candidates if ok]
    unbalanced_cands = [(v, y) for v, y, ok in candidates]

    if balanced_cands:
        _, sep = max(balanced_cands, key=lambda x: x[0])
    elif unbalanced_cands:
        _, sep = max(unbalanced_cands, key=lambda x: x[0])
        print("[WARN] No balanced separator — using brightest")
    else:
        return None

    print(f"[INFO] Separator (smoothed): y={sep}  brightness={smoothed[sep]:.0f}")
    return sep


def auto_slice(img: np.ndarray):
    h, w = img.shape[:2]
    portrait = h > w

    if portrait:
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        profile = gray.mean(axis=1)
        sep     = _find_separator(profile, h)
        if sep is not None:
            a, b = img[:sep], img[sep:]
        else:
            half = h // 2
            a, b = img[:half], img[h - half:]
            sep  = half
            print("[INFO] No separator — falling back to h//2 cut")
    else:
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        profile = gray.mean(axis=0)
        sep     = _find_separator(profile, w)
        if sep is not None:
            a, b = img[:, :sep], img[:, sep:]
        else:
            half = w // 2
            a, b = img[:, :half], img[:, w - half:]
            sep  = half
            print("[INFO] No separator — falling back to w//2 cut")

    if portrait:
        min_h   = min(a.shape[0], b.shape[0])
        a_start = sep - min_h
        b_start = sep
        a, b    = a[-min_h:], b[:min_h]
    else:
        min_w   = min(a.shape[1], b.shape[1])
        a_start = sep - min_w
        b_start = sep
        a, b    = a[:, -min_w:], b[:, :min_w]

    print(f"[INFO] Auto-sliced → A{a.shape[:2]}  B{b.shape[:2]}  "
          f"a_start={a_start}  b_start={b_start}")
    return a, b, a_start, b_start


# ─────────────────────────────────────────────────────────────────────────────
#  2.  ALIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    ga = _gray(cv2.resize(a, (512, 512)))
    gb = _gray(cv2.resize(b, (512, 512)))
    score, _ = ssim(ga, gb, full=True)
    return float(score)


def _warp_h(src, H, wh):
    return cv2.warpPerspective(src, H, wh,
                               flags=cv2.INTER_LANCZOS4,
                               borderMode=cv2.BORDER_REFLECT_101)


def _homography_ok(H, w, h):
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


def _stage1_scale(ref, tgt):
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
        print(f"[INFO] Stage-1: same ratio → Lanczos resize")
        return out
    scale   = min(w / wt, h / ht)
    nw, nh  = int(wt * scale), int(ht * scale)
    resized = cv2.resize(tgt, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    edge    = np.concatenate([resized[0].reshape(-1,3), resized[-1].reshape(-1,3),
                              resized[:,0].reshape(-1,3), resized[:,-1].reshape(-1,3)])
    pad_c   = tuple(int(x) for x in np.median(edge, axis=0))
    canvas  = np.full((h, w, 3), pad_c, dtype=np.uint8)
    y0, x0  = (h - nh) // 2, (w - nw) // 2
    canvas[y0:y0+nh, x0:x0+nw] = resized
    print(f"[INFO] Stage-1: different ratio → fit-and-pad")
    return canvas


def _match(g_ref, g_tgt, name):
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


def _stage2_features(ref, tgt):
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
        print(f"[INFO] Stage-2 {name}: accepted ({inliers} inliers)")
        warped  = _warp_h(tgt, H, (w, h))
        corners = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
        mapped  = cv2.perspectiveTransform(corners, H).reshape(-1,2)
        vy1     = min(h, int(np.floor(mapped[:,1].max())))
        vy1     = vy1 if vy1 > 10 else h
        return warped, (0, vy1), H
    print("[WARN] Stage-2: no usable homography")
    return tgt, (0, h), None


def _stage3_ecc(ref, tgt):
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
    H_full[0, 2] /= sc
    H_full[1, 2] /= sc
    if not _homography_ok(H_full, w, h):
        print("[WARN] Stage-3 ECC: insane result — skipped")
        return tgt
    return _warp_h(tgt, H_full, (w, h))


def align(ref, tgt, skip_ecc=True):
    s0 = _ssim(ref, tgt)
    print(f"[INFO] SSIM before alignment : {s0:.4f}")
    tgt = _stage1_scale(ref, tgt)
    s1  = _ssim(ref, tgt)
    print(f"[INFO] SSIM after  Stage-1   : {s1:.4f}")
    tgt2, valid_range, H = _stage2_features(ref, tgt)
    s2 = _ssim(ref, tgt2)
    if s2 >= s1 - 0.005:
        tgt, s_cur = tgt2, s2
    else:
        s_cur = s1; H = None; valid_range = (0, ref.shape[0])
        print("[INFO] Stage-2 made things worse — reverted")
    print(f"[INFO] SSIM after  Stage-2   : {s_cur:.4f}")
    if not skip_ecc:
        tgt3 = _stage3_ecc(ref, tgt)
        s3   = _ssim(ref, tgt3)
        if s3 > s_cur + 0.001:
            tgt, s_cur = tgt3, s3
            print(f"[INFO] SSIM after  Stage-3   : {s_cur:.4f}  (ECC applied)")
        else:
            print(f"[INFO] SSIM after  Stage-3   : {s3:.4f}  (ECC skipped)")
    return tgt, valid_range, H


# ─────────────────────────────────────────────────────────────────────────────
#  3.  DIFFERENCE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _auto_threshold(deltas, floor):
    if len(deltas) < 3:
        return floor, "too few candidates — using floor"
    s = sorted(deltas)
    if s[0] >= floor:
        if len(s) >= 3 and s[0] < floor + 6 and s[1] > 2.5 * s[0]:
            t = (s[0] + s[1]) / 2.0
            return t, f"near-floor outlier {s[0]:.1f} vs next {s[1]:.1f}"
        return floor, f"all deltas above floor {floor:.1f}"
    gaps = [s[i+1] - s[i] for i in range(len(s)-1)]
    top2 = sorted(gaps, reverse=True)[:2]
    idx  = int(np.argmax(gaps))
    nc   = idx + 1
    sc   = len(s) - nc
    dominant = (
        top2[0] > 20.0
        and (len(top2) < 2 or top2[0] >= 1.4 * top2[1])
        and nc >= 1 and sc >= 1
    )
    if dominant:
        t = (s[idx] + s[idx+1]) / 2.0
        return t, f"dominant gap {s[idx]:.1f}→{s[idx+1]:.1f}, dropping {nc} noise contour(s)"
    return floor, f"no dominant gap — keeping all above floor {floor:.1f}"


def _lab_delta_map(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    la    = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).astype(np.float32)
    lb    = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).astype(np.float32)
    delta = np.sqrt(np.sum((la - lb) ** 2, axis=2))
    mx    = delta.max()
    return (delta / mx * 255).astype(np.uint8) if mx > 0 else delta.astype(np.uint8)


def _hue_delta_map(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    hsva = cv2.cvtColor(a, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsvb = cv2.cvtColor(b, cv2.COLOR_BGR2HSV).astype(np.float32)
    ha, hb = hsva[:, :, 0], hsvb[:, :, 0]
    sa, sb = hsva[:, :, 1], hsvb[:, :, 1]
    diff_h = np.abs(ha - hb)
    diff_h = np.minimum(diff_h, 180.0 - diff_h)
    sat_mask = ((sa > HUE_SAT_MIN) & (sb > HUE_SAT_MIN)).astype(np.float32)
    diff_h   = diff_h * sat_mask
    print(f"[INFO] Hue-delta map: max={diff_h.max():.1f} deg  "
          f"coloured-px={int(sat_mask.sum())}/{a.shape[0] * a.shape[1]}")
    return diff_h


def _split_large_blob(blob_mask: np.ndarray, cdiff: np.ndarray,
                      max_r: int, h: int, w: int) -> list:
    """
    FIX A: When a contour's enclosing-circle radius exceeds max_r, use a
    distance-transform cascade to find tightly-separated sub-centres and
    return individual circles (each capped at max_r) instead of dropping
    the whole region.
    """
    dist = cv2.distanceTransform(blob_mask, cv2.DIST_L2, 5)
    if dist.max() < 3:
        return []

    for erode_px in (70, 50, 35, 20, 10):
        ke = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_px, erode_px))
        peaks = cv2.erode(blob_mask, ke)
        if peaks.sum() == 0:
            continue
        sub_cnts, _ = cv2.findContours(peaks, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if len(sub_cnts) < 2:
            continue

        result = []
        seen   = []
        for sc in sub_cnts:
            (cx, cy), _ = cv2.minEnclosingCircle(sc)
            cx, cy = int(cx), int(cy)
            # deduplicate by proximity
            if any(((cx - sx)**2 + (cy - sy)**2)**0.5 < max_r * 0.6
                   for sx, sy in seen):
                continue
            seen.append((cx, cy))
            r = min(erode_px + CIRCLE_PAD + 20, max_r)
            lm = np.zeros((h, w), dtype=np.uint8)
            cv2.circle(lm, (cx, cy), r, 255, -1)
            rgb_mean = cv2.mean(cdiff, mask=lm)[0]
            if rgb_mean > 5:
                result.append((cx, cy, r, rgb_mean))

        if result:
            print(f"[INFO]   Split → {len(result)} sub-circles "
                  f"(erode={erode_px})")
            return result

    # Fallback: single sub-circle at centroid of dist-transform peak
    peak_loc = np.unravel_index(dist.argmax(), dist.shape)
    cy, cx   = int(peak_loc[0]), int(peak_loc[1])
    r        = min(int(dist.max()) + CIRCLE_PAD, max_r)
    lm = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(lm, (cx, cy), r, 255, -1)
    rgb_mean = cv2.mean(cdiff, mask=lm)[0]
    if rgb_mean > 5:
        return [(cx, cy, r, rgb_mean)]
    return []


def detect(img_a: np.ndarray,
           img_b: np.ndarray,
           min_area: int      = 50,
           delta_floor: float = 7.0,   # FIX D: was 8.0
           valid_y_range=None):
    h, w = img_a.shape[:2]

    assert img_b.shape[:2] == (h, w), (
        f"img_b must be pre-aligned to {(h, w)}, got {img_b.shape[:2]}. "
        "Call align() before detect()."
    )

    vy0, vy1 = valid_y_range if valid_y_range else (0, h)
    vy0, vy1 = max(0, vy0), min(h, vy1)

    gray_a = _gray(img_a)
    gray_b = _gray(img_b)

    score, diff = ssim(gray_a, gray_b, full=True)
    print(f"[INFO] SSIM for detection    : {score:.4f}")
    inv = cv2.bitwise_not((diff * 255).clip(0, 255).astype(np.uint8))

    lab_diff = _lab_delta_map(img_a, img_b)

    hue_diff_deg = _hue_delta_map(img_a, img_b)
    thresh_hue   = (hue_diff_deg > HUE_FIXED_THRESH).astype(np.uint8) * 255
    k_hue = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                      (HUE_DILATE_KSIZE, HUE_DILATE_KSIZE))
    thresh_hue = cv2.morphologyEx(thresh_hue, cv2.MORPH_DILATE, k_hue)

    valid_ssim = inv[vy0:vy1, :]
    valid_lab  = lab_diff[vy0:vy1, :]
    otsu_ssim  = cv2.threshold(valid_ssim, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[0]
    otsu_lab   = cv2.threshold(valid_lab,  0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[0]
    _, thresh_ssim = cv2.threshold(inv,      otsu_ssim, 255, cv2.THRESH_BINARY)
    _, thresh_lab  = cv2.threshold(lab_diff, otsu_lab,  255, cv2.THRESH_BINARY)

    print(f"[INFO] Otsu SSIM={otsu_ssim:.0f}  Lab={otsu_lab:.0f}  "
          f"Hue=fixed@{HUE_FIXED_THRESH}+dilate{HUE_DILATE_KSIZE}")

    thresh = cv2.bitwise_or(thresh_ssim, thresh_lab)
    thresh = cv2.bitwise_or(thresh,      thresh_hue)

    k9 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k9)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k5)

    border = max(8, int(min(h, w) * 0.02))
    bmask  = np.zeros_like(thresh)
    bmask[border:h - border, border:w - border] = 255
    if vy0 > border:
        bmask[:vy0, :] = 0
    if vy1 < h - border:
        bmask[vy1:,  :] = 0
    thresh = cv2.bitwise_and(thresh, bmask)

    max_allowed_r = int(min(h, w) * MAX_BLOB_RADIUS_FRAC)
    cdiff_rgb     = np.mean(cv2.absdiff(img_a, img_b).astype(np.float32), axis=2)

    # ── FIX A: split oversized blobs instead of dropping them ────────────────
    pre_cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    extra_candidates = []   # (cx, cy, r, delta) tuples from split blobs
    for c in pre_cnts:
        (_, _), r = cv2.minEnclosingCircle(c)
        if r > max_allowed_r:
            blob_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(blob_mask, [c], -1, 255, cv2.FILLED)
            print(f"[INFO] Large blob r={int(r)} — attempting split …")
            subs = _split_large_blob(blob_mask, cdiff_rgb, max_allowed_r, h, w)
            for scx, scy, sr, sd in subs:
                extra_candidates.append((scx, scy, sr, sd))
            cv2.drawContours(thresh, [c], -1, 0, cv2.FILLED)
    # ── end FIX A ─────────────────────────────────────────────────────────────

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        m = np.zeros((h, w), dtype=np.uint8)
        cv2.drawContours(m, [cnt], -1, 255, cv2.FILLED)
        rgb_delta = cv2.mean(cdiff_rgb,    mask=m)[0]
        hue_delta = cv2.mean(hue_diff_deg, mask=m)[0]
        delta     = max(rgb_delta, hue_delta * HUE_SCORE_WEIGHT)
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        candidates.append((cnt, delta, int(cx), int(cy), int(r)))

    # Merge extra (split) candidates into main list as pseudo-contours
    # They are already filtered for delta>5; re-check floor later
    for scx, scy, sr, sd in extra_candidates:
        # represent as a simple rectangle contour centred at (scx, scy)
        candidates.append((None, sd, scx, scy, sr))

    if not candidates:
        print("[WARN] No candidates survived filtering.")
        return [], 0

    deltas = sorted(d for _, d, _, _, _ in candidates)
    print(f"[INFO] Candidates : {len(candidates)}  "
          f"deltas: {[round(d, 1) for d in deltas]}")

    threshold, reason = _auto_threshold(deltas, delta_floor)
    print(f"[INFO] Delta-threshold : {threshold:.1f}  ({reason})")

    surviving = [(cnt, delta, cx, cy, r)
                 for cnt, delta, cx, cy, r in candidates
                 if delta >= threshold]

    groups: list = []
    for cnt, delta, cx, cy, r in surviving:
        cx, cy = float(cx), float(cy)
        merged = False
        for grp in groups:
            if ((cx - grp[2]) ** 2 + (cy - grp[3]) ** 2) ** 0.5 < MERGE_RADIUS:
                grp[0].append((cx, cy, r))
                grp[1] = max(grp[1], delta)
                grp[2] = float(np.mean([s[0] for s in grp[0]]))
                grp[3] = float(np.mean([s[1] for s in grp[0]]))
                merged = True
                break
        if not merged:
            groups.append([[(cx, cy, r)], delta, cx, cy])

    print(f"[INFO] After merging: {len(groups)} groups")
    groups.sort(key=lambda g: g[1], reverse=True)

    if len(groups) >= 3:
        all_d = np.array([g[1] for g in groups])
        keep  = []
        for grp in groups:
            others  = all_d[all_d != grp[1]]
            med_oth = float(np.median(others)) if len(others) else grp[1]
            if grp[1] < LOW_DELTA_FRAC * med_oth:
                print(f"[INFO] Dropping low-delta group delta={grp[1]:.1f}")
            else:
                keep.append(grp)
        groups = keep

    circles = []
    for grp in groups:
        sub       = grp[0]
        centres   = np.array([[s[0], s[1]] for s in sub], dtype=np.float32)
        max_sub_r = max(s[2] for s in sub)
        if len(centres) == 1:
            cx, cy = centres[0]
            r = max(int(max_sub_r) + CIRCLE_PAD, 18)  # FIX E
        else:
            (cx, cy), span = cv2.minEnclosingCircle(centres.reshape(-1, 1, 2))
            r = max(int(span + max_sub_r) + CIRCLE_PAD, 18)  # FIX E
        if r > max_allowed_r:
            # cap rather than drop
            r = max_allowed_r
        circles.append((int(cx), int(cy), r))

    return circles, len(circles)


# ─────────────────────────────────────────────────────────────────────────────
#  3b.  LINE-DRAWING MODE
# ─────────────────────────────────────────────────────────────────────────────

_SATURATION_LINE_THRESHOLD = 20

def is_line_drawing(img: np.ndarray) -> bool:
    hsv      = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mean_sat = float(hsv[:, :, 1].mean())
    mode     = "line-drawing" if mean_sat < _SATURATION_LINE_THRESHOLD else "colour"
    print(f"[INFO] Mean saturation: {mean_sat:.1f}  → {mode} mode")
    return mean_sat < _SATURATION_LINE_THRESHOLD


def detect_line(img_a, img_b):
    LINE_SSIM_THRESH  = 30
    LINE_MORPH_KSIZE  = 3
    LINE_MIN_AREA     = 20
    LINE_DELTA_FLOOR  = 5.0
    LINE_MAX_DIFF_MIN = max(80, int(min(img_a.shape[:2]) * 0.45))
    LINE_NMS_RADIUS   = max(20, int(min(img_a.shape[:2]) * 0.12))

    h, w  = img_a.shape[:2]
    img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LANCZOS4)
    score, diff = ssim(_gray(img_a), _gray(img_b), full=True)
    print(f"[INFO] SSIM for detection    : {score:.4f}")
    inv      = cv2.bitwise_not((diff * 255).clip(0, 255).astype(np.uint8))
    _, thresh = cv2.threshold(inv, LINE_SSIM_THRESH, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (LINE_MORPH_KSIZE, LINE_MORPH_KSIZE))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,  k)
    border = max(8, int(min(h, w) * 0.02))
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
        x1 = max(0, cx-r-5); y1 = max(0, cy-r-5)
        x2 = min(w, cx+r+5); y2 = min(h, cy+r+5)
        peak = float(np.abs(ga[y1:y2, x1:x2] - gb[y1:y2, x1:x2]).max())
        if peak < LINE_MAX_DIFF_MIN:
            continue
        max_r = int(min(h, w) * 0.15)
        candidates.append((cx, cy, min(max(r + 15, 20), max_r), delta))
    candidates.sort(key=lambda x: -x[3])
    kept = []
    for cx, cy, r, d in candidates:
        if not any(((cx-kx)**2+(cy-ky)**2)**0.5 < LINE_NMS_RADIUS
                   for kx, ky, _, _ in kept):
            kept.append((cx, cy, r, d))
    circles = [(cx, cy, r) for cx, cy, r, _ in kept]
    return circles, len(kept)


# ─────────────────────────────────────────────────────────────────────────────
#  3c.  NUMBER GRID MODE
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_digit_grid(img_bgr: np.ndarray):
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError(
            "[ERROR] pytesseract is not installed.\n"
            "        pip install pytesseract\n"
            "        sudo apt install tesseract-ocr  (Linux)\n"
            "        brew install tesseract          (macOS)"
        )

    gray   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray   = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(gray, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 15, 8)
    if np.mean(binary) < 128:
        binary = cv2.bitwise_not(binary)

    cropped = _crop_grid_content(img_bgr, binary)

    cfg  = "--psm 6 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(
        Image.fromarray(cropped), config=cfg
    ).strip()

    if not text:
        print("[WARN] OCR returned empty string.")
        return None

    rows = []
    for line in text.splitlines():
        digits = re.findall(r'\d', line)
        if digits:
            rows.append(digits)

    if len(rows) < NUM_MIN_ROWS:
        print(f"[WARN] OCR returned only {len(rows)} rows — likely not a number grid.")
        return None

    col_counts      = [len(r) for r in rows]
    most_common_len = max(set(col_counts), key=col_counts.count)
    rows            = [r for r in rows if len(r) == most_common_len]

    if most_common_len < NUM_MIN_COLS or len(rows) < NUM_MIN_ROWS:
        print(f"[WARN] Grid too small after filtering: {len(rows)}×{most_common_len}")
        return None

    print(f"[INFO] OCR grid: {len(rows)} rows × {most_common_len} cols")
    return rows


def _crop_grid_content(img_bgr: np.ndarray, binary: np.ndarray) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    PAD  = NUM_CELL_PAD

    cnts, _ = cv2.findContours(cv2.bitwise_not(binary),
                                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(largest)
        if cw > w * 0.7 and ch > h * 0.7:
            x1 = max(0,   x  + PAD)
            y1 = max(0,   y  + PAD)
            x2 = min(w,   x  + cw - PAD)
            y2 = min(h,   y  + ch - PAD)
            cropped = binary[y1:y2, x1:x2]
            print(f"[INFO] Grid border crop: ({x1},{y1})→({x2},{y2})")
            return cropped

    return binary[PAD:h-PAD, PAD:w-PAD]


def _grid_cell_centres(panel_shape: tuple,
                        n_rows: int,
                        n_cols: int,
                        grid_crop_coords):
    h, w = panel_shape[:2]
    if grid_crop_coords:
        x1, y1, x2, y2 = grid_crop_coords
    else:
        x1, y1, x2, y2 = 0, 0, w, h

    cell_w = (x2 - x1) / n_cols
    cell_h = (y2 - y1) / n_rows

    centres = []
    for r in range(n_rows):
        row = []
        for c in range(n_cols):
            cx = int(x1 + (c + 0.5) * cell_w)
            cy = int(y1 + (r + 0.5) * cell_h)
            row.append((cx, cy))
        centres.append(row)
    return centres


def _find_grid_crop_coords(img_bgr: np.ndarray):
    h, w = img_bgr.shape[:2]
    PAD  = NUM_CELL_PAD
    gray   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 15, 8)
    if np.mean(binary) < 128:
        binary = cv2.bitwise_not(binary)
    cnts, _ = cv2.findContours(cv2.bitwise_not(binary),
                                cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        largest = max(cnts, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(largest)
        if cw > w * 0.7 and ch > h * 0.7:
            return (max(0, x+PAD), max(0, y+PAD),
                    min(w, x+cw-PAD), min(h, y+ch-PAD))
    return None


def detect_number_grid(img_a: np.ndarray,
                        img_b: np.ndarray) -> tuple:
    print("[INFO] Number-grid mode: running OCR on both panels...")

    grid_a = _ocr_digit_grid(img_a)
    grid_b = _ocr_digit_grid(img_b)

    if grid_a is None or grid_b is None:
        print("[ERROR] OCR failed on one or both panels. Falling back to colour detection.")
        circles, count = detect(img_a, img_b)
        dummy = [[]]
        return circles, circles, count, dummy, dummy

    n_rows = min(len(grid_a), len(grid_b))
    n_cols = min(len(grid_a[0]), len(grid_b[0]))
    grid_a = [row[:n_cols] for row in grid_a[:n_rows]]
    grid_b = [row[:n_cols] for row in grid_b[:n_rows]]

    crop_a = _find_grid_crop_coords(img_a)
    crop_b = _find_grid_crop_coords(img_b)

    centres_a = _grid_cell_centres(img_a.shape, n_rows, n_cols, crop_a)
    centres_b = _grid_cell_centres(img_b.shape, n_rows, n_cols, crop_b)

    h_a, w_a = img_a.shape[:2]
    if crop_a:
        x1, y1, x2, y2 = crop_a
        cell_w = (x2 - x1) / n_cols
        cell_h = (y2 - y1) / n_rows
    else:
        cell_w = w_a / n_cols
        cell_h = h_a / n_rows
    radius = max(12, int(min(cell_w, cell_h) * 0.55))

    diffs_a = []
    diffs_b = []
    print(f"[INFO] Comparing {n_rows}×{n_cols} grids...")
    for r in range(n_rows):
        for c in range(n_cols):
            va = grid_a[r][c]
            vb = grid_b[r][c]
            if va != vb:
                cx_a, cy_a = centres_a[r][c]
                cx_b, cy_b = centres_b[r][c]
                diffs_a.append((cx_a, cy_a, radius))
                diffs_b.append((cx_b, cy_b, radius))
                print(f"       Diff at row={r+1} col={c+1}: top={va!r}  bottom={vb!r}")

    count = len(diffs_a)
    print(f"[INFO] Number-grid diffs found: {count}")
    return diffs_a, diffs_b, count, centres_a, centres_b


# ─────────────────────────────────────────────────────────────────────────────
#  4.  OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

def random_run_color() -> tuple:
    h = random.uniform(0, 360)
    s = random.uniform(0.80, 1.00)
    v = random.uniform(0.80, 1.00)
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    r, g, b = [(c,x,0),(x,c,0),(0,c,x),(0,x,c),(x,0,c),(c,0,x)][int(h//60)%6]
    return (int((r+m)*255), int((g+m)*255), int((b+m)*255))


def _load_font(path, size):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_circles_on_panel(panel_pil, circles, color, H_inv=None):
    """FIX F: No number badges — circles only."""
    pw, ph = panel_pil.size
    if H_inv is not None and len(circles) > 0:
        pts    = np.float32([[cx, cy] for cx, cy, r in circles]).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(pts, H_inv).reshape(-1, 2)
        circles = [(int(np.clip(mx, 0, pw-1)), int(np.clip(my, 0, ph-1)), r)
                   for (mx, my), (_, _, r) in zip(mapped, circles)]
    img   = panel_pil.copy()
    draw  = ImageDraw.Draw(img)
    for cx, cy, r in circles:
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color, width=4)
    return img


def _khmer_digits(n: int) -> str:
    return str(n).translate(str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩"))


def make_khmer_banner(width: int, count: int) -> Image.Image:
    BH    = 80
    text  = f"រកឃើញភាពខុសគ្នា {_khmer_digits(count)} កន្លែង"
    banner = Image.new("RGB", (width, BH), (30, 30, 50))
    draw   = ImageDraw.Draw(banner)
    kfont, kfont_path = pick_random_khmer_font(40)
    print(f"[INFO] Khmer banner font : {os.path.basename(kfont_path)}")
    bb     = draw.textbbox((0, 0), text, font=kfont)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    tx     = (width - tw) // 2 - bb[0]
    ty     = (BH    - th) // 2 - bb[1]
    draw.text((tx+2, ty+2), text, font=kfont, fill=(10,10,20))
    draw.text((tx,   ty  ), text, font=kfont, fill=(255,215,60))
    return banner


def add_watermark(img: Image.Image) -> Image.Image:
    text  = "ចម្លើយពីក្មួយ និរន្ត"
    w, h  = img.size
    wm    = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(wm)
    font_size = max(24, w // 18)
    font, _ = pick_random_khmer_font(font_size)
    bb   = draw.textbbox((0, 0), text, font=font)
    tw   = bb[2] - bb[0]
    th   = bb[3] - bb[1]
    step_x = int(tw * 1.6)
    step_y = int(th * 3.5)
    angle  = -30
    for row, y0 in enumerate(range(-th * 2, h + th * 2, step_y)):
        x_shift = (row % 2) * (step_x // 2)
        for x0 in range(-tw - x_shift, w + tw, step_x):
            tile = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(tile)
            for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                tdraw.text((10 - bb[0] + dx, 10 - bb[1] + dy),
                           text, font=font, fill=(255,255,255,60))
            tdraw.text((10 - bb[0], 10 - bb[1]),
                       text, font=font, fill=(180,180,180,55))
            rotated = tile.rotate(angle, expand=True)
            wm.paste(rotated, (x0, y0), rotated)
    out = img.convert("RGBA")
    out = Image.alpha_composite(out, wm)
    return out.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
#  5.  OUTPUT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_stacked_output(combined_bgr, img_a, img_b_aligned,
                          circles, a_start, b_start, color, count,
                          H=None):
    BH = 80
    oh, ow = combined_bgr.shape[:2]
    ph     = img_a.shape[0]
    pil_a  = Image.fromarray(cv2.cvtColor(img_a, cv2.COLOR_BGR2RGB))
    pil_a  = draw_circles_on_panel(pil_a, circles, color, H_inv=None)
    H_inv  = np.linalg.inv(H) if H is not None else None
    b_slice = combined_bgr[b_start:b_start + ph, :]
    pil_b   = Image.fromarray(cv2.cvtColor(b_slice, cv2.COLOR_BGR2RGB))
    pil_b   = draw_circles_on_panel(pil_b, circles, color, H_inv=H_inv)
    base   = Image.fromarray(cv2.cvtColor(combined_bgr, cv2.COLOR_BGR2RGB))
    canvas = Image.new("RGB", (ow, BH + oh), (30, 30, 50))
    canvas.paste(base,  (0, BH))
    canvas.paste(pil_a, (0, BH + a_start))
    canvas.paste(pil_b, (0, BH + b_start))
    canvas.paste(make_khmer_banner(ow, count), (0, 0))
    return canvas


def build_stacked_output_numgrid(combined_bgr, img_a,
                                  circles_a, circles_b,
                                  a_start, b_start, color, count):
    BH      = 80
    oh, ow  = combined_bgr.shape[:2]
    ph      = img_a.shape[0]
    pil_a   = Image.fromarray(cv2.cvtColor(img_a, cv2.COLOR_BGR2RGB))
    pil_a   = draw_circles_on_panel(pil_a, circles_a, color, H_inv=None)
    b_slice = combined_bgr[b_start:b_start + ph, :]
    pil_b   = Image.fromarray(cv2.cvtColor(b_slice, cv2.COLOR_BGR2RGB))
    pil_b   = draw_circles_on_panel(pil_b, circles_b, color, H_inv=None)
    base    = Image.fromarray(cv2.cvtColor(combined_bgr, cv2.COLOR_BGR2RGB))
    canvas  = Image.new("RGB", (ow, BH + oh), (30, 30, 50))
    canvas.paste(base,  (0, BH))
    canvas.paste(pil_a, (0, BH + a_start))
    canvas.paste(pil_b, (0, BH + b_start))
    canvas.paste(make_khmer_banner(ow, count), (0, 0))
    return canvas


def build_sidebyside_output(img_a, img_b_original, img_b_aligned,
                             circles, color, count, H=None):
    BH, GAP = 80, 6
    h, w    = img_a.shape[:2]
    H_inv   = np.linalg.inv(H) if H is not None else None
    pil_a   = Image.fromarray(cv2.cvtColor(img_a,          cv2.COLOR_BGR2RGB))
    pil_b   = Image.fromarray(cv2.cvtColor(img_b_original, cv2.COLOR_BGR2RGB))
    pil_a   = draw_circles_on_panel(pil_a, circles, color, H_inv=None)
    pil_b   = draw_circles_on_panel(pil_b, circles, color, H_inv=H_inv)
    total_w = w * 2 + GAP
    canvas  = Image.new("RGB", (total_w, BH + h), (30, 30, 50))
    canvas.paste(pil_a, (0,       BH))
    canvas.paste(pil_b, (w + GAP, BH))
    ImageDraw.Draw(canvas).rectangle([w, BH, w+GAP, BH+h], fill=(180,180,180))
    canvas.paste(make_khmer_banner(total_w, count), (0, 0))
    return canvas


def build_sidebyside_output_numgrid(img_a, img_b, circles_a, circles_b, color, count):
    BH, GAP  = 80, 6
    h_a, w_a = img_a.shape[:2]
    h_b, w_b = img_b.shape[:2]
    h        = max(h_a, h_b)
    pil_a    = Image.fromarray(cv2.cvtColor(img_a, cv2.COLOR_BGR2RGB))
    pil_b    = Image.fromarray(cv2.cvtColor(img_b, cv2.COLOR_BGR2RGB))
    pil_a    = draw_circles_on_panel(pil_a, circles_a, color)
    pil_b    = draw_circles_on_panel(pil_b, circles_b, color)
    total_w  = w_a + GAP + w_b
    canvas   = Image.new("RGB", (total_w, BH + h), (30, 30, 50))
    canvas.paste(pil_a, (0,        BH))
    canvas.paste(pil_b, (w_a+GAP,  BH))
    ImageDraw.Draw(canvas).rectangle([w_a, BH, w_a+GAP, BH+h], fill=(180,180,180))
    canvas.paste(make_khmer_banner(total_w, count), (0, 0))
    return canvas


# ─────────────────────────────────────────────────────────────────────────────
#  6.  CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Automatic spot-the-difference detector (v2 – fixed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python spot_the_difference.py puzzle.jpg
  python spot_the_difference.py original.png modified.png
  python spot_the_difference.py numgrid.png --mode number
  python spot_the_difference.py a.png b.png --mode number --output result.png
  python spot_the_difference.py puzzle.jpg --ecc
  python spot_the_difference.py puzzle.jpg --no-align
        """,
    )
    p.add_argument("images",  nargs="+", metavar="IMAGE")
    p.add_argument("--output",      default="circled_result.png")
    p.add_argument("--min-area",    type=int,   default=50)
    p.add_argument("--delta-floor", type=float, default=7.0)  # FIX D
    p.add_argument("--mode",
                   choices=["auto", "colour", "line", "number"],
                   default="auto")
    p.add_argument("--no-align", action="store_true")
    p.add_argument("--ecc",      action="store_true")
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

    img_b_original = img_b.copy()
    color          = random_run_color()
    print(f"[INFO] Run colour : RGB{color}")

    # ── NUMBER GRID MODE ─────────────────────────────────────────────────────
    if args.mode == "number":
        print("[INFO] Mode: number-grid (OCR diff)")
        circles_a, circles_b, count, _ca, _cb = detect_number_grid(img_a, img_b)

        if two_image_mode:
            result = build_sidebyside_output_numgrid(
                img_a, img_b, circles_a, circles_b, color, count)
        else:
            result = build_stacked_output_numgrid(
                combined, img_a,
                circles_a, circles_b,
                a_start, b_start, color, count)

        result = add_watermark(result)
        result.save(args.output, quality=95)
        print(); print("=" * 45)
        print(f"  Mode              : number-grid")
        print(f"  Differences found : {count}")
        print(f"  Run colour        : RGB{color}")
        print(f"  Saved to          : {args.output!r}")
        print("=" * 45)
        return

    # ── VISUAL MODES (colour / line / auto) ──────────────────────────────────
    if args.no_align:
        img_b_aligned = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]),
                                   interpolation=cv2.INTER_LANCZOS4)
        valid_y_range = (0, img_a.shape[0])
        H_align       = None
        print("[INFO] Alignment skipped (--no-align)")
    else:
        img_b_aligned, valid_y_range, H_align = align(img_a, img_b, skip_ecc=not args.ecc)

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
                                delta_floor=args.delta_floor,
                                valid_y_range=valid_y_range)

    if two_image_mode:
        result = build_sidebyside_output(img_a, img_b_original, img_b_aligned,
                                         circles, color, count, H=H_align)
    else:
        result = build_stacked_output(combined, img_a, img_b_aligned,
                                      circles, a_start, b_start, color, count,
                                      H=H_align)

    result = add_watermark(result)
    result.save(args.output, quality=95)

    print(); print("=" * 45)
    print(f"  Mode              : {'line-drawing' if line_mode else 'colour'}")
    print(f"  Differences found : {count}")
    print(f"  Run colour        : RGB{color}")
    print(f"  Saved to          : {args.output!r}")
    print("=" * 45)


if __name__ == "__main__":
    main()