#!/usr/bin/env python3
import os

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''

import sys
import time
import json
import asyncio
import platform
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from google.cloud import vision
from google import genai

parent_dir = Path(__file__).resolve().parent.parent
dotenv_path = parent_dir / '.env'
load_dotenv(dotenv_path=dotenv_path)

GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', str(parent_dir / 'credentials.json')).replace('\ufeff', '').strip()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').replace('\ufeff', '').strip()

IMAGE_FOLDER = Path(__file__).resolve().parent / 'khmer_test_images'
OUTPUT_FOLDER = Path(__file__).resolve().parent / 'results'
OUTPUT_FOLDER.mkdir(exist_ok=True)

# ANSI colors
RED       = "\033[91m"
YELLOW    = "\033[93m"
CYAN      = "\033[96m"
WHITE     = "\033[97m"
BG_RED    = "\033[41m"
BG_YELLOW = "\033[43m"
BOLD      = "\033[1m"
RESET     = "\033[0m"

VISUAL_KEYWORDS_EN = [
    "draw", "drawing", "sketch", "diagram", "chart", "graph", "picture", "image",
    "illustrate", "illustration", "show", "display", "plot", "figure", "shape",
    "color", "colour", "shade", "fill", "mark", "circle", "highlight", "label",
    "map", "table", "grid", "visual", "arrange", "layout", "design", "pattern",
    "symbol", "icon", "arrow", "line", "box", "tick", "cross", "check"
]

VISUAL_KEYWORDS_KH = [
    "គូរ",       # draw
    "គូស",       # draw/sketch
    "រូប",       # picture/image
    "តារាង",     # table/chart
    "គំនូរ",     # drawing/sketch
    "សញ្ញា",     # symbol/sign
    "ដ្យាក្រាម", # diagram
    "ផែនទី",     # map
    "ក្រាហ្វ",   # graph
    "ចំណុច",     # point/dot
    "បង្ហាញ",    # show/display
    "ឆែក",       # check/tick
    "ដាក់",      # place/put
    "ពណ៌",       # color
    "លាប",       # paint/color in
    "គំរូ",      # pattern/model
    "ជួរ",       # row/column
    "ខ្នាត",     # scale/size
]

ANALYSIS_PROMPT = (
    "The following text is in Khmer. Read it carefully.\n"
    "First, determine: does this question require a VISUAL answer (drawing, diagram, chart, coloring, "
    "sketching, marking on a grid, labeling a figure, filling a table, etc.)? "
    "Or is it a TEXTUAL answer (a word, number, sentence, calculation, etc.)?\n\n"
    "Regardless of the type, always provide a full explanation and the final answer in Khmer.\n\n"
    "Respond ONLY in this exact format:\n"
    "TYPE: VISUAL or TEXTUAL\n"
    "EXPLANATION: <brief reasoning in Khmer>\n"
    "ANSWER: <final answer in Khmer>\n"
)

def safe_print(text, fallback="[text contains characters that cannot be displayed in this terminal]"):
    try:
        print(text)
    except UnicodeEncodeError:
        print(fallback)

def copy_to_clipboard(text):
    current_os = platform.system()
    try:
        if current_os == 'Windows':
            subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
        elif current_os == 'Darwin':
            subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
        elif current_os == 'Linux':
            try:
                subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
            except FileNotFoundError:
                subprocess.run(['xsel', '--clipboard', '--input'], input=text.encode('utf-8'), check=True)
        else:
            print(f"  [clipboard not supported on OS: {current_os}]")
            return False
        return True
    except FileNotFoundError:
        if current_os == 'Linux':
            print(f"  [clipboard failed: install xclip with 'sudo apt install xclip']")
        return False
    except Exception as e:
        print(f"  [clipboard failed: {e}]")
        return False

def parse_response(response_text):
    answer_type = "TEXTUAL"
    explanation = ""
    answer = response_text.strip()

    lines = response_text.strip().splitlines()
    explanation_lines = []
    answer_lines = []
    in_answer = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TYPE:"):
            val = stripped[len("TYPE:"):].strip().upper()
            answer_type = "VISUAL" if "VISUAL" in val else "TEXTUAL"
        elif stripped.startswith("ANSWER:"):
            in_answer = True
            remainder = stripped[len("ANSWER:"):].strip()
            if remainder:
                answer_lines.append(remainder)
        elif stripped.startswith("EXPLANATION:"):
            in_answer = False
            remainder = stripped[len("EXPLANATION:"):].strip()
            if remainder:
                explanation_lines.append(remainder)
        elif in_answer:
            answer_lines.append(line)
        else:
            explanation_lines.append(line)

    if answer_lines:
        explanation = "\n".join(explanation_lines).strip()
        answer = "\n".join(answer_lines).strip()

    return answer_type, explanation, answer

def keyword_check(text):
    text_lower = text.lower()
    for kw in VISUAL_KEYWORDS_EN:
        if kw in text_lower:
            return True
    for kw in VISUAL_KEYWORDS_KH:
        if kw in text:
            return True
    return False

def print_visual_warning():
    width = 60
    border = "█" * width
    lines = [
        "",
        f"{BG_RED}{BOLD}{WHITE}{border}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + ' ' * (width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + '⚠  VISUAL ANSWER REQUIRED  ⚠'.center(width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + ' ' * (width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + 'This question needs a drawing,'.center(width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + 'diagram, chart, or visual output!'.center(width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + ' ' * (width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + 'READ EXPLANATION THEN DRAW'.center(width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{'█' + ' ' * (width-2) + '█'}{RESET}",
        f"{BG_RED}{BOLD}{WHITE}{border}{RESET}",
        "",
    ]
    for _ in range(3):
        for line in lines:
            safe_print(line)
        time.sleep(0.2)
    for line in lines:
        safe_print(line)

def setup():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
    vision_client = vision.ImageAnnotatorClient()
    return vision_client, genai.Client(api_key=GEMINI_API_KEY)

def get_newest_image():
    images = (
        list(IMAGE_FOLDER.glob('*.png')) +
        list(IMAGE_FOLDER.glob('*.jpg')) +
        list(IMAGE_FOLDER.glob('*.jpeg'))
    )
    if not images:
        return None
    return max(images, key=lambda f: f.stat().st_mtime)

async def process(image_path, vision_client, genai_client):
    pipeline_start = time.time()

    print(f"  [1/2] OCR: sending to Google Cloud Vision...")
    with open(image_path, 'rb') as f:
        image = vision.Image(content=f.read())

    response = vision_client.document_text_detection(image=image)
    extracted_text = response.full_text_annotation.text.replace('\ufeff', '')
    ocr_time = time.time() - pipeline_start

    print(f"  [2/2] LLM: sending to Gemini Flash...")
    answer_start = time.time()

    answer_response = await genai_client.aio.models.generate_content(
        model="gemini-3.5-flash",
        contents=f"{ANALYSIS_PROMPT}\n\n{extracted_text}"
    )

    raw_response = answer_response.text.strip().replace('\ufeff', '')
    answer_type, explanation, answer = parse_response(raw_response)

    keyword_hit = keyword_check(extracted_text)
    if keyword_hit and answer_type == "TEXTUAL":
        answer_type = "VISUAL"

    answer_time = time.time() - answer_start
    total_time = time.time() - pipeline_start

    return {
        'image': image_path.name,
        'extracted_text': extracted_text,
        'answer_type': answer_type,
        'explanation': explanation,
        'answer': answer,
        'keyword_triggered': keyword_hit,
        'timing': {
            'ocr_seconds': round(ocr_time, 3),
            'llm_seconds': round(answer_time, 3),
            'total_seconds': round(total_time, 3)
        },
        'status': 'SUCCESS',
        'timestamp': datetime.now().isoformat()
    }

async def main_async():
    print(f"  [OS detected: {platform.system()}]")

    if not Path(GOOGLE_APPLICATION_CREDENTIALS).exists():
        print(f"ERROR: credentials file not found: {GOOGLE_APPLICATION_CREDENTIALS}")
        sys.exit(1)
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY missing from .env")
        sys.exit(1)
    if not IMAGE_FOLDER.exists():
        print(f"ERROR: image folder not found: {IMAGE_FOLDER}")
        sys.exit(1)

    image_path = get_newest_image()
    if not image_path:
        print(f"ERROR: no images found in {IMAGE_FOLDER}")
        sys.exit(1)

    print(f"\nImage   : {image_path.name}")
    print(f"Started : {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 60)

    vision_client, genai_client = setup()

    try:
        result = await process(image_path, vision_client, genai_client)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    t = result['timing']

    print("\n--- EXTRACTED TEXT (QUESTION) ---")
    safe_print(result['extracted_text'].strip())
    print("-" * 60)

    if result['answer_type'] == "VISUAL":
        print_visual_warning()
        print(f"{BG_YELLOW}{BOLD}{' EXPLANATION (read before drawing) '.center(60)}{RESET}")
    else:
        print(f"\n{CYAN}{BOLD}[ ANSWER TYPE: TEXTUAL ]{RESET}")

    if result['explanation']:
        print(f"\n{YELLOW}--- EXPLANATION ---{RESET}")
        safe_print(result['explanation'])
        print("-" * 60)

    print(f"\n{BOLD}>>> ANSWER <<<{RESET}")
    safe_print(result['answer'])
    print(f"{BOLD}>>> END <<<{RESET}\n")

    copied = copy_to_clipboard(result['answer'])
    if copied:
        print(f"{CYAN}Answer copied to clipboard. ({platform.system()}){RESET}")

    print(f"\nTotal: {t['total_seconds']}s  (OCR: {t['ocr_seconds']}s | LLM: {t['llm_seconds']}s)")
    if result.get('keyword_triggered'):
        print(f"{YELLOW}[keyword scan also flagged this as visual]{RESET}")

    output_file = OUTPUT_FOLDER / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved to: {output_file}")

if __name__ == '__main__':
    asyncio.run(main_async())
