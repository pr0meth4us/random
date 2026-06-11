#!/usr/bin/env python3
"""
process_images.py
-----------------
Recursively scans a folder of images, runs OCR (Google Cloud Vision),
then sends each result to Gemini to:
  - Classify as TEXTUAL or VISUAL
  - Generate a short keyword title  ← ALWAYS populated, with multiple fallback layers
  - Transcribe full text (if TEXTUAL)
  - Write a specific description of what the image is about

Outputs a JSON array: filename, type, title, transcription, description, ocr_seconds, llm_seconds, total_seconds

MODES:
  python process_images.py          → process ALL images in folder
  python process_images.py --newest → process only the single newest image
"""

import os
import re
import sys
import time
import json
import base64
import asyncio
import platform
from pathlib import Path
from dotenv import load_dotenv

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from google.cloud import vision
from google import genai

# ── Config ────────────────────────────────────────────────────────────────────
# Directory layout:
#   project/
#   ├── .env                  ← API keys (one level above this script)
#   ├── credentials.json      ← GCP service account
#   └── processor/
#       ├── process_images.py ← this script
#       ├── folder/           ← input images (default, override via IMAGE_FOLDER)
#       └── results/          ← JSON output (auto-created)

SCRIPT_DIR  = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

load_dotenv(dotenv_path=PROJECT_DIR / '.env')

GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    'GOOGLE_APPLICATION_CREDENTIALS',
    str(PROJECT_DIR / 'credentials.json')
).replace('\ufeff', '').strip()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').replace('\ufeff', '').strip()

IMAGE_FOLDER = Path(
    os.getenv('IMAGE_FOLDER', str(SCRIPT_DIR / 'folder3'))
).resolve()

OUTPUT_JSON = Path(
    os.getenv('OUTPUT_JSON', str(SCRIPT_DIR / 'results' / 'output.json'))
).resolve()

SUPPORTED_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tiff'}
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '5'))

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ── Prompts ───────────────────────────────────────────────────────────────────
ANALYSIS_PROMPT = """You are given an image and its OCR-extracted text (may be Khmer, English, or mixed).
Look at BOTH the image visually AND the text to answer.

Your job:
1. Decide if this requires a VISUAL answer (spot-the-difference, drawing, diagram, coloring, labeling, etc.)
   OR a TEXTUAL answer (word problem, math question, announcement, list, document, etc.)
2. If TEXTUAL: transcribe the full content cleanly.
3. Give a 3-5 word keyword title (e.g. "Digit 8 Count Math", "Jungle Spot Difference", "Sisters Allowance Problem").
   This MUST be specific and meaningful — never leave it blank or generic like "Image Analysis".
4. Write 1 plain-English sentence describing what is actually shown/asked — mention specific visual content:
   - Spot-the-difference: name the scene (e.g. "Spot-the-difference puzzle of a jungle village with monkeys and huts")
   - Drawing task: describe what to draw (e.g. "Student must draw and label parts of a flower")
   - Math problem: state what it asks (e.g. "Count how many times digit 8 appears from 1 to 100")
   - Word problem: summarize it (e.g. "Two sisters share $15/week, Lina gets $2 more — find each amount")
   - List/announcement: say what it is (e.g. "7 prize winners of the crow-and-faces riddle challenge")
   - Document: state the subject (e.g. "Cambodian government decree assigning a minister as UN envoy")
   NEVER say "the image contains" or "two images" without saying what those images show.
   ALWAYS name the specific scene, subject, or topic visible in the image.

Respond ONLY in this exact JSON format (no markdown fences, no extra keys):
{
  "type": "TEXTUAL" or "VISUAL",
  "title": "<3-5 word keyword title>",
  "transcription": "<full clean text if TEXTUAL, else empty string>",
  "description": "<1 sentence describing the specific content/scene/question>"
}

OCR text:
"""

VISUAL_PROMPT = (
    "Look at this image carefully. You must respond in this exact JSON format (no markdown fences):\n"
    "{\n"
    "  \"type\": \"VISUAL\",\n"
    "  \"title\": \"<3-5 word keyword title — REQUIRED, must be specific>\",\n"
    "  \"transcription\": \"\",\n"
    "  \"description\": \"<1 sentence: name the specific scene and what the student must do>\"\n"
    "}\n\n"
    "For title — be specific and keyword-style (e.g. 'Jungle Spot Difference', 'Flower Parts Label', 'Cambodia Map Draw').\n"
    "NEVER leave title blank or use generic words like 'Image' or 'Visual Task'.\n\n"
    "For description — be specific about what you see:\n"
    "- Spot-the-difference: name what's in the pictures (e.g. 'Spot-the-difference of a beach scene with coconut trees and fishing boats')\n"
    "- Drawing task: say what to draw (e.g. 'Student must draw and color a map of Cambodia')\n"
    "- Diagram: name it (e.g. 'Label the parts of a human eye diagram')\n"
    "NEVER say 'the image contains' — say what it SHOWS and ASKS."
)

# ── Visual keyword detection ───────────────────────────────────────────────────
VISUAL_KEYWORDS_EN = [
    "draw","drawing","sketch","diagram","chart","graph","picture","image",
    "illustrate","illustration","show","display","plot","figure","shape",
    "color","colour","shade","fill","mark","circle","highlight","label",
    "map","table","grid","visual","arrange","layout","design","pattern",
    "symbol","icon","arrow","line","box","tick","cross","check"
]
VISUAL_KEYWORDS_KH = [
    "គូរ","គូស","រូប","តារាង","គំនូរ","សញ្ញា","ដ្យាក្រាម",
    "ផែនទី","ក្រាហ្វ","ចំណុច","បង្ហាញ","ឆែក","ដាក់","ពណ៌",
    "លាប","គំរូ","ជួរ","ខ្នាត",
]

MIME_MAP = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png',  '.webp': 'image/webp',
    '.bmp': 'image/bmp',  '.gif':  'image/gif',
    '.tiff': 'image/tiff',
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def keyword_check(text: str) -> bool:
    tl = text.lower()
    return (
        any(kw in tl for kw in VISUAL_KEYWORDS_EN) or
        any(kw in text for kw in VISUAL_KEYWORDS_KH)
    )


def safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print("[unprintable characters in output]")


def to_b64(img_bytes: bytes) -> str:
    return base64.standard_b64encode(img_bytes).decode('utf-8')


def strip_fences(raw: str) -> str:
    """Remove markdown code fences and leading 'json' labels."""
    raw = raw.strip('` \n')
    if raw.startswith('json'):
        raw = raw[4:].lstrip()
    return raw


def extract_title_from_text(raw_response: str, ocr_text: str) -> str:
    """
    Multi-layer title fallback when JSON parsing fails or title is missing/blank.

    Layer 1: Try to regex-extract "title": "..." from malformed JSON.
    Layer 2: Pull the first meaningful non-whitespace line from OCR text.
    Layer 3: Derive from filename stub passed via ocr_text sentinel.
    Layer 4: Hard fallback "Untitled Image".
    """
    # Layer 1 — regex scrape from raw LLM response
    m = re.search(r'"title"\s*:\s*"([^"]{3,})"', raw_response)
    if m:
        candidate = m.group(1).strip()
        if candidate and candidate.lower() not in ('', 'none', 'n/a', 'image', 'visual task', 'image analysis'):
            return candidate[:80]

    # Layer 2 — first non-trivial line of OCR text
    if ocr_text:
        for line in ocr_text.splitlines():
            line = line.strip()
            if len(line) >= 4:
                # Trim to ~5 words
                words = line.split()[:5]
                return ' '.join(words)

    # Layer 4 — hard fallback
    return 'Untitled Image'


def parse_llm_response(raw: str, ocr_text: str) -> dict:
    """
    Parse Gemini JSON response. Always guarantees a non-empty 'title'.
    Falls back gracefully on any parse failure.
    """
    clean = strip_fences(raw.strip().replace('\ufeff', ''))

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        # Attempt partial recovery
        parsed = {
            'type':          'TEXTUAL' if ocr_text else 'VISUAL',
            'title':         '',
            'transcription': ocr_text,
            'description':   clean[:200],
        }

    # Guarantee title is always populated
    title = str(parsed.get('title', '')).strip()
    if not title or title.lower() in ('', 'none', 'n/a', 'image', 'visual task', 'image analysis'):
        title = extract_title_from_text(raw, ocr_text)
    parsed['title'] = title

    return parsed


# ── Setup clients ─────────────────────────────────────────────────────────────

def setup():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
    return vision.ImageAnnotatorClient(), genai.Client(api_key=GEMINI_API_KEY)


# ── Collect images ────────────────────────────────────────────────────────────

def collect_images(folder: Path, newest_only: bool) -> list[Path]:
    images = [
        p for p in folder.rglob('*')
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    ]
    if not images:
        return []
    if newest_only:
        return [max(images, key=lambda p: p.stat().st_mtime)]
    return sorted(images)


# ── Process a single image ────────────────────────────────────────────────────

async def process_image(
    image_path: Path,
    vision_client,
    genai_client,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
) -> dict:
    rel = image_path.relative_to(IMAGE_FOLDER)
    tag = f"[{index}/{total}] {rel}"

    result = {
        'filename':      str(rel),
        'type':          'ERROR',
        'title':         '',
        'transcription': '',
        'description':   '',
        'ocr_seconds':   0.0,
        'llm_seconds':   0.0,
        'total_seconds': 0.0,
        'error':         '',
    }

    t0 = time.time()
    try:
        # ── 1. OCR ────────────────────────────────────────────────────────────
        safe_print(f"  {CYAN}{tag}{RESET}  → OCR …")
        with open(image_path, 'rb') as f:
            img_bytes = f.read()

        vision_image = vision.Image(content=img_bytes)
        ocr_response = vision_client.document_text_detection(image=vision_image)
        extracted    = ocr_response.full_text_annotation.text.replace('\ufeff', '').strip()
        ocr_time     = time.time() - t0

        mime_type = MIME_MAP.get(image_path.suffix.lower(), 'image/jpeg')
        img_b64   = to_b64(img_bytes)

        # ── 2. Gemini ─────────────────────────────────────────────────────────
        safe_print(f"  {CYAN}{tag}{RESET}  → Gemini …")
        llm_start = time.time()

        if not extracted:
            # No OCR text — vision-only prompt
            prompt_parts = [
                {"inline_data": {"mime_type": mime_type, "data": img_b64}},
                {"text": VISUAL_PROMPT},
            ]
        else:
            # Has OCR text — send image + text together
            prompt_parts = [
                {"inline_data": {"mime_type": mime_type, "data": img_b64}},
                {"text": ANALYSIS_PROMPT + extracted},
            ]

        async with semaphore:
            llm_response = await genai_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=[{"parts": prompt_parts}],
            )

        raw_text = llm_response.text or ''
        llm_time = time.time() - llm_start

        # Parse with guaranteed title population
        parsed = parse_llm_response(raw_text, extracted)

        img_type = parsed.get('type', 'TEXTUAL' if extracted else 'VISUAL').upper()
        if img_type not in ('TEXTUAL', 'VISUAL'):
            img_type = 'TEXTUAL' if extracted else 'VISUAL'

        # Keyword override: OCR text contains visual task indicators
        if extracted and img_type == 'TEXTUAL' and keyword_check(extracted):
            img_type = 'VISUAL'

        result.update({
            'type':          img_type,
            'title':         parsed['title'],                                         # always non-empty
            'transcription': parsed.get('transcription', '') if img_type == 'TEXTUAL' else '',
            'description':   parsed.get('description', ''),
            'ocr_seconds':   round(ocr_time, 3),
            'llm_seconds':   round(llm_time, 3),
            'total_seconds': round(time.time() - t0, 3),
        })

        icon = (
            f"{GREEN}✓ TEXTUAL{RESET}" if img_type == 'TEXTUAL'
            else f"{YELLOW}⚠ VISUAL{RESET}"
        )
        title_display = result['title'][:40] + ('…' if len(result['title']) > 40 else '')
        safe_print(
            f"  {tag}  {icon}  \"{title_display}\"  ({result['total_seconds']}s)"
        )

    except Exception as e:
        result['error'] = str(e)
        result['total_seconds'] = round(time.time() - t0, 3)
        safe_print(f"  {RED}{tag}  ERROR: {e}{RESET}")

    return result


# ── JSON output ───────────────────────────────────────────────────────────────

def init_json(path: Path):
    """Open the output file and write the opening bracket."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, 'w', encoding='utf-8')
    fh.write('[\n')
    return fh

def append_json_record(fh, record: dict, is_first: bool):
    """Append one record to the streaming JSON array."""
    prefix = '' if is_first else ',\n'
    fh.write(prefix + json.dumps(record, ensure_ascii=False, indent=2))
    fh.flush()

def close_json(fh):
    """Write the closing bracket and close the file."""
    fh.write('\n]\n')
    fh.close()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    newest_only = '--newest' in sys.argv

    print(f"\n{BOLD}Image Batch Processor{RESET}")
    print(f"  Mode     : {'newest only' if newest_only else 'all images'}")
    print(f"  Platform : {platform.system()}")
    print(f"  Folder   : {IMAGE_FOLDER}")
    print(f"  Output   : {OUTPUT_JSON}")

    missing = []
    if not Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        missing.append(f"credentials not found: {GOOGLE_APPLICATION_CREDENTIALS}")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY missing from .env")
    if not IMAGE_FOLDER.exists():
        missing.append(f"image folder not found: {IMAGE_FOLDER}")
    if missing:
        for m in missing:
            print(f"{RED}ERROR: {m}{RESET}")
        sys.exit(1)

    images = collect_images(IMAGE_FOLDER, newest_only)
    if not images:
        print(f"{YELLOW}No images found in {IMAGE_FOLDER}{RESET}")
        sys.exit(0)

    if newest_only:
        print(f"\n  Newest   : {images[0].name}\n")
    else:
        print(f"\n  Found {len(images)} image(s). Starting …\n")
    print("-" * 70)

    vision_client, genai_client = setup()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    fh        = init_json(OUTPUT_JSON)
    results, errors, is_first = [], 0, True

    try:
        tasks = [
            process_image(img, vision_client, genai_client, semaphore, i + 1, len(images))
            for i, img in enumerate(images)
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            append_json_record(fh, result, is_first)
            is_first = False
            results.append(result)
            if result['error']:
                errors += 1
    finally:
        close_json(fh)

    print("\n" + "=" * 70)
    print(f"{BOLD}DONE{RESET}")
    print(f"  Total    : {len(images)}")
    print(f"  TEXTUAL  : {sum(1 for r in results if r['type'] == 'TEXTUAL')}")
    print(f"  VISUAL   : {sum(1 for r in results if r['type'] == 'VISUAL')}")
    print(f"  Errors   : {errors}")
    avg = sum(r['total_seconds'] for r in results) / len(results) if results else 0
    print(f"  Avg/img  : {avg:.2f}s")

    # Show any blank titles that fell through to fallback
    blank_titles = [r for r in results if not r['title'] or r['title'] == 'Untitled Image']
    if blank_titles:
        print(f"\n  {YELLOW}⚠ {len(blank_titles)} image(s) got fallback titles:{RESET}")
        for r in blank_titles:
            print(f"    {r['filename']}")

    print(f"\n  {GREEN}JSON → {OUTPUT_JSON}{RESET}\n")


if __name__ == '__main__':
    asyncio.run(main())