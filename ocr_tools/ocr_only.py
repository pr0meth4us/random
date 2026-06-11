#!/usr/bin/env python3
"""
ocr_only.py — Pure OCR pipeline using Google Cloud Vision.
Supports: PNG, JPG, JPEG, HEIC, HEIF, PDF (multi-page)
Output:   Per-page text, per-file text, or both — saved as JSON + plain .txt

Key feature: DYNAMIC CHUNKED PROCESSING
  Large PDFs are automatically split into memory-safe chunks at runtime.
  The chunk size is calculated from available RAM so the process never
  gets OOM-killed regardless of PDF size or DPI.

  Formula:
    bytes_per_page  = (width_px * height_px * 3)   <- RGB at target DPI
    safe_ram_budget = available_ram * RAM_SAFETY_FACTOR (default 0.4)
    chunk_size      = max(1, floor(safe_ram_budget / bytes_per_page))

  Each chunk is converted -> OCR'd -> written to disk -> freed before the
  next chunk loads, so peak RAM stays flat even on 200-page files.

  Override with --chunk-size N to force a fixed chunk size, or
  --no-chunk to disable chunking and revert to the old all-at-once
  behaviour (not recommended for large PDFs).

HEIC/HEIF support:
  Google Cloud Vision does not accept HEIC/HEIF natively. The pipeline
  automatically converts HEIC/HEIF to JPEG in-memory before sending to
  the API. Conversion uses pillow-heif (preferred) or pyheif as a
  fallback. Install one of them:
    pip install pillow-heif    <- recommended, pre-built wheels on macOS/Linux
    pip install pyheif         <- alternative
"""

import os
import sys
import gc
import io
import json
import math
import time
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent
GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    'GOOGLE_APPLICATION_CREDENTIALS', str(PROJECT_DIR / 'credentials.json')
)
OUTPUT_FOLDER = Path(__file__).resolve().parent / 'results'
OUTPUT_FOLDER.mkdir(exist_ok=True)

SUPPORTED_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.heic', '.heif'}
SUPPORTED_EXTS       = SUPPORTED_IMAGE_EXTS | {'.pdf'}
GRANULARITY_CHOICES  = ('page', 'file', 'both')

# Fraction of available RAM we're willing to use for image buffers.
RAM_SAFETY_FACTOR = 0.4
# ──────────────────────────────────────────────────────────────────────────────


def setup_vision_client():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
    from google.cloud import vision
    return vision.ImageAnnotatorClient()


# ── HEIC/HEIF conversion ──────────────────────────────────────────────────────

def convert_heic_to_jpeg(heic_bytes: bytes) -> bytes:
    """
    Convert HEIC/HEIF image bytes -> JPEG bytes.

    Tries pillow-heif first (pip install pillow-heif), then pyheif
    (pip install pyheif). Raises RuntimeError if neither is installed.

    pillow-heif registers itself as a Pillow plugin so the conversion is
    just a normal Pillow open -> save. pyheif returns raw pixel data that
    we wrap in a Pillow Image manually.
    """
    # ── pillow-heif (preferred) ───────────────────────────────────────────────
    try:
        import pillow_heif                        # noqa: F401  (registers plugin)
        from PIL import Image

        pillow_heif.register_heif_opener()        # idempotent
        img = Image.open(io.BytesIO(heic_bytes))
        buf = io.BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=95)
        return buf.getvalue()

    except ImportError:
        pass   # try next library

    # ── pyheif (fallback) ─────────────────────────────────────────────────────
    try:
        import pyheif
        from PIL import Image

        heif_file = pyheif.read_heif(heic_bytes)
        img = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
            heif_file.mode,
            heif_file.stride,
        )
        buf = io.BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=95)
        return buf.getvalue()

    except ImportError:
        pass

    raise RuntimeError(
        "HEIC/HEIF conversion requires pillow-heif or pyheif.\n"
        "  pip install pillow-heif   <- recommended\n"
        "  pip install pyheif        <- alternative"
    )


# ── Memory helpers ────────────────────────────────────────────────────────────

def available_ram_bytes() -> int:
    """Return bytes of RAM currently available (not just free)."""
    try:
        import psutil
        return psutil.virtual_memory().available
    except ImportError:
        # Fallback: assume a conservative 1 GB if psutil is missing
        return 1 * 1024 ** 3


def estimate_page_ram(dpi: int, page_w_pt: float = 595, page_h_pt: float = 842) -> int:
    """
    Estimate uncompressed RGB RAM footprint for one page at the given DPI.
    Defaults assume A4 (595 x 842 pt).
    """
    scale   = dpi / 72.0
    w_px    = int(page_w_pt * scale)
    h_px    = int(page_h_pt * scale)
    return w_px * h_px * 3   # 3 bytes per pixel (RGB)


def auto_chunk_size(dpi: int, pdf_path: Path | None = None) -> int:
    """
    Dynamically compute a safe chunk size (pages per batch) based on
    available RAM and estimated per-page RAM footprint at the given DPI.
    """
    ram = available_ram_bytes()
    budget = int(ram * RAM_SAFETY_FACTOR)

    page_w_pt, page_h_pt = 595.0, 842.0   # A4 defaults

    if pdf_path is not None:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            if len(doc) > 0:
                rect = doc[0].rect
                page_w_pt = rect.width
                page_h_pt = rect.height
            doc.close()
        except Exception:
            pass   # keep A4 defaults

    per_page = estimate_page_ram(dpi, page_w_pt, page_h_pt)
    chunk    = max(1, math.floor(budget / per_page))

    ram_gb   = ram / 1024 ** 3
    ppram_mb = per_page / 1024 ** 2
    print(
        f"  [chunk] Available RAM : {ram_gb:.2f} GB  |  "
        f"Per-page estimate : {ppram_mb:.1f} MB  |  "
        f"Safe chunk size : {chunk} page(s)"
    )
    return chunk


# ── PDF helpers ───────────────────────────────────────────────────────────────

def _pdf_page_count(pdf_path: Path) -> int:
    """Return total page count without rasterising anything."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        n = len(doc)
        doc.close()
        return n
    except ImportError:
        pass

    try:
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass

    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(str(pdf_path))
        return int(info.get('Pages', 0))
    except Exception:
        return 0


def pdf_chunk_to_images(
    pdf_path: Path,
    first_page: int,   # 1-based, inclusive
    last_page: int,    # 1-based, inclusive
    dpi: int,
) -> list[bytes]:
    """
    Rasterise only pages [first_page, last_page] of the PDF.
    Returns PNG bytes for each page in the range.
    """
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(
            str(pdf_path), dpi=dpi,
            first_page=first_page, last_page=last_page,
        )
        result = []
        for page in pages:
            buf = io.BytesIO()
            page.save(buf, format='PNG')
            result.append(buf.getvalue())
        return result

    except ImportError:
        pass

    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        result = []
        for page_idx in range(first_page - 1, last_page):   # fitz is 0-based
            pix = doc[page_idx].get_pixmap(matrix=mat, alpha=False)
            result.append(pix.tobytes('png'))
            pix = None   # release immediately
        doc.close()
        return result

    except ImportError:
        raise RuntimeError(
            "PDF support requires either pdf2image+poppler or PyMuPDF.\n"
            "  pip install pdf2image   (+ poppler via brew/apt)\n"
            "  pip install pymupdf"
        )


# ── Preprocessing core ────────────────────────────────────────────────────────

def preprocess_image_bytes(image_bytes: bytes) -> bytes:
    """
    Adaptive binarization via OpenCV; falls back to Pillow contrast boost.
    Returns original bytes if no image library is available.
    """
    try:
        import cv2
        import numpy as np

        nparr = np.frombuffer(image_bytes, np.uint8)
        img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        _, enc = cv2.imencode('.png', thresh)
        return enc.tobytes()

    except ImportError:
        try:
            from PIL import Image, ImageEnhance
            img      = Image.open(io.BytesIO(image_bytes)).convert('L')
            enhanced = ImageEnhance.Contrast(img).enhance(2.0)
            buf      = io.BytesIO()
            enhanced.save(buf, format='PNG')
            return buf.getvalue()
        except Exception:
            return image_bytes


# ── Layout-Aware parsing ──────────────────────────────────────────────────────

def extract_layout_aware_text(full_text_annotation) -> str:
    """
    Geometrically sort Vision API blocks to preserve reading order
    in multi-column layouts.
    """
    if not full_text_annotation or not hasattr(full_text_annotation, 'pages'):
        return ""

    paragraphs = []
    for page in full_text_annotation.pages:
        blocks_sorted = sorted(
            page.blocks,
            key=lambda b: (b.bounding_box.vertices[0].y // 50,
                           b.bounding_box.vertices[0].x)
        )
        for block in blocks_sorted:
            for paragraph in block.paragraphs:
                para_text = ""
                for word in paragraph.words:
                    word_text = "".join(s.text for s in word.symbols)
                    brk = word.symbols[-1].property.detected_break if word.symbols else None
                    if brk:
                        from google.cloud import vision as _v
                        BT = _v.TextAnnotation.DetectedBreak.BreakType
                        if brk.type_ in (BT.SPACE, BT.SURE_SPACE):
                            word_text += " "
                        elif brk.type_ in (BT.LINE_BREAK, BT.EOL_SURE_SPACE):
                            word_text += "\n"
                    else:
                        word_text += " "
                    para_text += word_text
                paragraphs.append(para_text.strip())

    return "\n\n".join(paragraphs)


# ── OCR core ─────────────────────────────────────────────────────────────────

def ocr_image_bytes(image_bytes: bytes, client, languages: list[str], use_layout: bool) -> str:
    """Send one page image to Cloud Vision and return extracted text."""
    from google.cloud import vision

    image    = vision.Image(content=image_bytes)
    context  = vision.ImageContext(language_hints=languages)
    response = client.document_text_detection(image=image, image_context=context)

    if response.error.message:
        raise RuntimeError(f"Vision API error: {response.error.message}")

    full_annotation = response.full_text_annotation
    if not full_annotation:
        return ""

    if use_layout:
        layout_text = extract_layout_aware_text(full_annotation)
        if layout_text.strip():
            return layout_text

    return full_annotation.text or ""


def ocr_file(
    file_path: Path,
    client,
    languages: list[str],
    use_layout: bool,
    preprocess: bool,
    dpi: int = 400,
    chunk_size: int | None = None,   # None = auto-detect
    no_chunk: bool = False,
) -> list[dict]:
    """
    OCR a single file (image or PDF).
    Returns a list of page dicts: { 'page', 'text', 'ocr_seconds' }.

    HEIC/HEIF files are converted to JPEG in-memory before OCR because
    Google Cloud Vision does not accept the HEIC/HEIF container format.

    For PDFs:
      - Counts total pages first (fast, no rasterisation).
      - Computes a safe chunk size from available RAM (unless overridden).
      - Processes one chunk at a time, GC-ing after each chunk so peak
        RAM stays bounded regardless of total page count.
    """
    ext = file_path.suffix.lower()

    # ── Images: simple single-page path ──────────────────────────────────────
    if ext in SUPPORTED_IMAGE_EXTS:
        img_bytes = file_path.read_bytes()

        # Convert HEIC/HEIF -> JPEG before sending to Vision API.
        # Vision accepts JPEG, PNG, GIF, BMP, WEBP, RAW, ICO, PDF, TIFF
        # but NOT HEIC/HEIF — conversion must happen client-side.
        if ext in ('.heic', '.heif'):
            print(f"  -> Converting {ext.upper()} -> JPEG...", end=' ', flush=True)
            t_conv = time.time()
            img_bytes = convert_heic_to_jpeg(img_bytes)
            print(f"done ({round(time.time() - t_conv, 3)}s, {len(img_bytes) // 1024} KB)")

        if preprocess:
            img_bytes = preprocess_image_bytes(img_bytes)

        t0      = time.time()
        text    = ocr_image_bytes(img_bytes, client, languages, use_layout)
        elapsed = round(time.time() - t0, 3)
        print(f"  OCR page 1/1... {elapsed}s  ({len(text)} chars)")
        return [{'page': 1, 'text': text, 'ocr_seconds': elapsed}]

    if ext != '.pdf':
        raise ValueError(f"Unsupported file type: {ext}")

    # ── PDFs: chunked path ────────────────────────────────────────────────────
    total_pages = _pdf_page_count(file_path)
    if total_pages == 0:
        print("  WARNING: Could not determine page count; loading entire PDF.")
        total_pages = None

    if total_pages:
        print(f"  -> PDF has {total_pages} page(s)")

    # Determine effective chunk size
    if no_chunk:
        eff_chunk = total_pages or 9999
        print(f"  -> Chunking disabled - loading all {eff_chunk} page(s) at once")
    elif chunk_size is not None:
        eff_chunk = chunk_size
        print(f"  -> Forced chunk size : {eff_chunk} page(s)")
    else:
        eff_chunk = auto_chunk_size(dpi, file_path)

    # Build chunk ranges
    if total_pages:
        chunks = [
            (start, min(start + eff_chunk - 1, total_pages))
            for start in range(1, total_pages + 1, eff_chunk)
        ]
        n_chunks = len(chunks)
    else:
        # Unknown total - we'll discover as we go
        chunks   = None
        n_chunks = '?'

    pages_out: list[dict] = []

    if chunks is not None:
        # ── Known-length chunked loop ─────────────────────────────────────────
        for chunk_idx, (first, last) in enumerate(chunks, start=1):
            n_in_chunk = last - first + 1
            print(
                f"\n  -- Chunk {chunk_idx}/{n_chunks}  "
                f"(pages {first}-{last}, {n_in_chunk} page(s)) --"
            )
            t_conv = time.time()
            chunk_images = pdf_chunk_to_images(file_path, first, last, dpi)
            print(f"     Rasterised in {round(time.time()-t_conv,2)}s")

            for local_idx, img_bytes in enumerate(chunk_images):
                page_num = first + local_idx
                label    = f"page {page_num}/{total_pages}"

                if preprocess:
                    print(f"  -> Preprocessing {label}...", end=' ', flush=True)
                    tp = time.time()
                    img_bytes = preprocess_image_bytes(img_bytes)
                    print(f"done ({round(time.time()-tp,3)}s)")

                print(f"  OCR {label}...", end=' ', flush=True)
                t0      = time.time()
                text    = ocr_image_bytes(img_bytes, client, languages, use_layout)
                elapsed = round(time.time() - t0, 3)
                print(f"{elapsed}s  ({len(text)} chars)")

                pages_out.append({'page': page_num, 'text': text, 'ocr_seconds': elapsed})
                img_bytes = None   # release reference immediately

            chunk_images = None
            gc.collect()    # explicitly free the chunk before loading the next

    else:
        # ── Unknown-length fallback: stream one chunk at a time ───────────────
        page_cursor = 1
        chunk_idx   = 0
        while True:
            first = page_cursor
            last  = page_cursor + eff_chunk - 1
            chunk_idx += 1
            print(f"\n  -- Chunk {chunk_idx}/?  (pages {first}-{last}) --")
            try:
                chunk_images = pdf_chunk_to_images(file_path, first, last, dpi)
            except Exception:
                break   # past the end of the document

            if not chunk_images:
                break

            for local_idx, img_bytes in enumerate(chunk_images):
                page_num = first + local_idx
                label    = f"page {page_num}/?"

                if preprocess:
                    img_bytes = preprocess_image_bytes(img_bytes)

                print(f"  OCR {label}...", end=' ', flush=True)
                t0      = time.time()
                text    = ocr_image_bytes(img_bytes, client, languages, use_layout)
                elapsed = round(time.time() - t0, 3)
                print(f"{elapsed}s  ({len(text)} chars)")
                pages_out.append({'page': page_num, 'text': text, 'ocr_seconds': elapsed})
                img_bytes = None

            page_cursor += len(chunk_images)
            chunk_images = None
            gc.collect()

            if len(pages_out) % eff_chunk != 0:
                break   # last chunk was partial -> we're done

    return pages_out


# ── Output helpers ────────────────────────────────────────────────────────────

def _base_name(file_path: Path) -> str:
    return f"{file_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def save_results_by_page(file_path: Path, pages: list[dict]) -> tuple[Path, Path]:
    """One JSON + one TXT with per-page section headers."""
    base      = _base_name(file_path)
    json_path = OUTPUT_FOLDER / f"{base}.json"
    txt_path  = OUTPUT_FOLDER / f"{base}.txt"

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'source':      file_path.name,
            'pages':       len(pages),
            'timestamp':   datetime.now().isoformat(),
            'granularity': 'page',
            'results':     pages,
        }, f, indent=2, ensure_ascii=False)

    with open(txt_path, 'w', encoding='utf-8') as f:
        for p in pages:
            if len(pages) > 1:
                f.write(f"{'='*60}\n  PAGE {p['page']} of {len(pages)}\n{'='*60}\n\n")
            f.write(p['text'].strip())
            f.write('\n\n')

    return json_path, txt_path


def save_results_by_file(file_path: Path, pages: list[dict]) -> tuple[Path, Path]:
    """Merge all pages into a single flat text block."""
    base      = _base_name(file_path)
    json_path = OUTPUT_FOLDER / f"{base}_combined.json"
    txt_path  = OUTPUT_FOLDER / f"{base}_combined.txt"

    full_text = "\n\n".join(p['text'].strip() for p in pages)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'source':           file_path.name,
            'pages':            len(pages),
            'timestamp':        datetime.now().isoformat(),
            'granularity':      'file',
            'total_chars':      len(full_text),
            'total_ocr_secs':   round(sum(p['ocr_seconds'] for p in pages), 3),
            'page_char_counts': [len(p['text']) for p in pages],
            'text':             full_text,
        }, f, indent=2, ensure_ascii=False)

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(full_text)
        f.write('\n')

    return json_path, txt_path


def save_results(
    file_path: Path,
    pages: list[dict],
    granularity: str,
) -> dict[str, tuple[Path, Path]]:
    out = {}
    if granularity in ('page', 'both'):
        out['page'] = save_results_by_page(file_path, pages)
    if granularity in ('file', 'both'):
        out['file'] = save_results_by_file(file_path, pages)
    return out


# ── Input resolution ──────────────────────────────────────────────────────────

def resolve_inputs(args_inputs: list[str]) -> list[Path]:
    if not args_inputs:
        default_folder = Path(__file__).resolve().parent / 'khmer_test_images'
        if not default_folder.exists():
            print(f"ERROR: No input given and {default_folder} not found.")
            sys.exit(1)
        candidates = [f for f in default_folder.iterdir()
                      if f.suffix.lower() in SUPPORTED_EXTS]
        if not candidates:
            print(f"ERROR: No supported files in {default_folder}")
            sys.exit(1)
        newest = max(candidates, key=lambda f: f.stat().st_mtime)
        print(f"No input specified -- using newest file: {newest.name}")
        return [newest]

    paths = []
    for raw in args_inputs:
        p = Path(raw)
        if p.is_dir():
            found = sorted(f for f in p.iterdir() if f.suffix.lower() in SUPPORTED_EXTS)
            if not found:
                print(f"WARNING: No supported files in directory {p}")
            paths.extend(found)
        elif p.is_file():
            if p.suffix.lower() not in SUPPORTED_EXTS:
                print(f"WARNING: Skipping unsupported file {p.name}")
            else:
                paths.append(p)
        else:
            print(f"WARNING: {p} does not exist -- skipping")

    if not paths:
        print("ERROR: No valid input files found.")
        sys.exit(1)

    return paths


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "OCR pipeline (Cloud Vision) with dynamic chunked PDF processing.\n"
            "Large PDFs are automatically split into RAM-safe chunks at runtime.\n"
            "HEIC/HEIF images are converted to JPEG in-memory before OCR."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'inputs', nargs='*',
        help='File(s) or folder(s) to OCR. Omit to use newest file in ./khmer_test_images'
    )
    parser.add_argument(
        '--dpi', type=int, default=400,
        help='DPI for PDF rasterisation (default: 400)'
    )
    parser.add_argument(
        '--chunk-size', type=int, default=None, metavar='N',
        help=(
            'Force a fixed chunk size of N pages per batch. '
            'Overrides auto-detection. '
            'Use when you want predictable behaviour regardless of available RAM.'
        )
    )
    parser.add_argument(
        '--no-chunk', action='store_true',
        help=(
            'Disable chunking entirely and load all pages at once. '
            'NOT recommended for large PDFs -- may cause OOM kill.'
        )
    )
    parser.add_argument(
        '--no-txt', action='store_true',
        help='Skip saving the plain .txt output'
    )
    parser.add_argument(
        '--lang', type=str, default='km,en',
        help='Comma-separated language hints for Vision API (default: km,en)'
    )
    parser.add_argument(
        '--no-layout', action='store_true',
        help='Disable layout-aware geometric block sorting'
    )
    parser.add_argument(
        '--preprocess', action='store_true',
        help='Enable adaptive image binarization/contrast enhancement'
    )
    parser.add_argument(
        '--granularity', choices=GRANULARITY_CHOICES, default='both',
        help=(
            '"page" = per-page outputs, '
            '"file" = one merged output, '
            '"both" = produce both (default)'
        )
    )
    args = parser.parse_args()

    if not Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        print(f"ERROR: Credentials not found at {GOOGLE_APPLICATION_CREDENTIALS}")
        sys.exit(1)

    languages  = [lang.strip() for lang in args.lang.split(',') if lang.strip()]
    use_layout = not args.no_layout
    files      = resolve_inputs(args.inputs)
    client     = setup_vision_client()

    for file_path in files:
        print(f"\n{'─'*55}")
        print(f"File : {file_path.name}")
        print(f"Type : {file_path.suffix.upper().lstrip('.')}")
        print(f"{'─'*55}")

        t_start = time.time()
        try:
            pages = ocr_file(
                file_path, client, languages, use_layout, args.preprocess,
                dpi=args.dpi,
                chunk_size=args.chunk_size,
                no_chunk=args.no_chunk,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        total   = round(time.time() - t_start, 3)
        outputs = save_results(file_path, pages, args.granularity)

        print(f"\n  Total time  : {total}s across {len(pages)} page(s)")
        print(f"  Granularity : {args.granularity}")

        if 'page' in outputs:
            jp, tp = outputs['page']
            print(f"  [page] JSON : {jp}")
            if not args.no_txt:
                print(f"  [page] TXT  : {tp}")

        if 'file' in outputs:
            jf, tf = outputs['file']
            print(f"  [file] JSON : {jf}")
            if not args.no_txt:
                print(f"  [file] TXT  : {tf}")

        # Preview first 20 lines of first page
        print(f"\n{'─'*55}")
        for p in pages[:3]:
            if len(pages) > 1:
                print(f"\n  -- Page {p['page']} --")
            lines = p['text'].strip().splitlines()
            for line in lines[:20]:
                print(f"  {line}")
            if len(lines) > 20:
                print(f"  ... (+{len(lines)-20} more lines)")

        if len(pages) > 3:
            print(f"\n  ... ({len(pages)-3} more pages not shown in preview)")

    print(f"\nDone. Results in: {OUTPUT_FOLDER.resolve()}")


if __name__ == '__main__':
    main()