import os
import fitz
import json
import sqlite3
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import vision

pdf_path = '/Users/nicksng/code/random/ក្រុមប្រឹក្សាជាតិភាសាខ្មែរ_ពាក្យបច្ចេកវិទ្យា.pdf'
output_dir = '/Users/nicksng/code/random/nckl_ocr_output'
os.makedirs(output_dir, exist_ok=True)

json_output_path = os.path.join(output_dir, 'nckl_tech_terms_pages.json')
md_output_path = os.path.join(output_dir, 'nckl_tech_terms_ocr.md')
db_output_path = os.path.join(output_dir, 'nckl_tech_terms.db')

print("Opening PDF...")
doc = fitz.open(pdf_path)
total_pages = len(doc)
print(f"Total PDF pages: {total_pages}")

client = vision.ImageAnnotatorClient()

def process_page(page_idx):
    page = doc[page_idx]
    # DPI 200 provides ideal resolution for Vision API OCR
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes('png')
    
    image = vision.Image(content=img_bytes)
    response = client.document_text_detection(image=image)
    
    page_text = ""
    if response.full_text_annotation:
        page_text = response.full_text_annotation.text
        
    return page_idx + 1, page_text

print(f"Processing all {total_pages} pages using Google Cloud Vision API...")
start_time = time.time()
pages_data = {}

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(process_page, i): i + 1 for i in range(total_pages)}
    completed_count = 0
    for future in as_completed(futures):
        page_num = futures[future]
        try:
            p_num, text = future.result()
            pages_data[p_num] = text
            completed_count += 1
            if completed_count % 10 == 0 or completed_count == total_pages:
                print(f"Progress: {completed_count}/{total_pages} pages processed ({completed_count/total_pages*100:.1f}%)")
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            pages_data[page_num] = ""

elapsed = time.time() - start_time
print(f"\nOCR completed in {elapsed:.2f} seconds!")

# Sort by page number
sorted_pages = {p: pages_data[p] for p in sorted(pages_data.keys())}

# Save raw pages to JSON
with open(json_output_path, 'w', encoding='utf-8') as f:
    json.dump(sorted_pages, f, ensure_ascii=False, indent=2)
print(f"Saved raw page OCR to: {json_output_path}")

# Save full OCR text to Markdown
with open(md_output_path, 'w', encoding='utf-8') as f:
    f.write("# ក្រុមប្រឹក្សាជាតិភាសាខ្មែរ - ពាក្យបច្ចេកវិទ្យា (Full OCR Transcription)\n\n")
    for p_num, text in sorted_pages.items():
        f.write(f"## Page {p_num}\n\n")
        f.write(text.strip() if text else "*(No text detected)*")
        f.write("\n\n---\n\n")
print(f"Saved Markdown OCR document to: {md_output_path}")

# Build SQLite Index with Full-Text Search (FTS5)
print("\nBuilding SQLite Index Database...")
if os.path.exists(db_output_path):
    os.remove(db_output_path)

conn = sqlite3.connect(db_output_path)
cur = conn.cursor()

# Table for pages
cur.execute("""
CREATE TABLE pages (
    page_number INTEGER PRIMARY KEY,
    content TEXT
)
""")

# FTS5 table for full-text search across all pages
cur.execute("""
CREATE VIRTUAL TABLE pages_fts USING fts5(
    page_number UNINDEXED,
    content
)
""")

# Table for structured term entries
cur.execute("""
CREATE TABLE terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_number INTEGER,
    term_english TEXT,
    term_khmer TEXT,
    full_entry TEXT
)
""")

# FTS5 table for structured terms search
cur.execute("""
CREATE VIRTUAL TABLE terms_fts USING fts5(
    term_id UNINDEXED,
    page_number UNINDEXED,
    term_english,
    term_khmer,
    full_entry
)
""")

# Populate pages and pages_fts
for p_num, content in sorted_pages.items():
    cur.execute("INSERT INTO pages (page_number, content) VALUES (?, ?)", (p_num, content))
    cur.execute("INSERT INTO pages_fts (page_number, content) VALUES (?, ?)", (p_num, content))

# Parse lines to extract terms (English & Khmer pairs)
# Pattern matching English word followed by Khmer or line pairs
term_count = 0
for p_num, content in sorted_pages.items():
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        # Identify lines containing English terms (letters, spaces, punctuation) and Khmer script
        english_match = re.search(r'([A-Za-z0-9\s\-\_\.\(\)\,\/\:\;]+)', line)
        khmer_match = re.search(r'([\u1780-\u17FF\u19E0-\u19FF]+[\s\u1780-\u17FF\u19E0-\u19FF]*)', line)
        
        if english_match and khmer_match:
            eng_part = english_match.group(1).strip()
            khm_part = khmer_match.group(1).strip()
            if len(eng_part) > 1 and len(khm_part) > 1:
                cur.execute(
                    "INSERT INTO terms (page_number, term_english, term_khmer, full_entry) VALUES (?, ?, ?, ?)",
                    (p_num, eng_part, khm_part, line)
                )
                term_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO terms_fts (term_id, page_number, term_english, term_khmer, full_entry) VALUES (?, ?, ?, ?, ?)",
                    (term_id, p_num, eng_part, khm_part, line)
                )
                term_count += 1

conn.commit()
conn.close()

print(f"Database built successfully at: {db_output_path}")
print(f"Indexed {len(sorted_pages)} pages and extracted {term_count} terminology entry candidates!")
