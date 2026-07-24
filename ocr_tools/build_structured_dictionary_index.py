import os
import json
import sqlite3
import re

json_path = '/Users/nicksng/code/random/nckl_ocr_output/nckl_tech_terms_pages.json'
db_path = '/Users/nicksng/code/random/nckl_ocr_output/nckl_tech_terms.db'

with open(json_path, 'r', encoding='utf-8') as f:
    pages = json.load(f)

# Re-create database with rich schema
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE pages (
    page_number INTEGER PRIMARY KEY,
    content TEXT
)
""")

cur.execute("""
CREATE TABLE dictionary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_number TEXT,
    khmer_term TEXT,
    english_term TEXT,
    french_term TEXT,
    definition TEXT,
    page_number INTEGER,
    raw_block TEXT
)
""")

cur.execute("""
CREATE VIRTUAL TABLE dictionary_fts USING fts5(
    entry_id UNINDEXED,
    page_number UNINDEXED,
    khmer_term,
    english_term,
    french_term,
    definition
)
""")

# Khmer to Western digits mapping
khmer_digits = {'០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4', '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'}

def to_western_num(s):
    res = ""
    for ch in s:
        res += khmer_digits.get(ch, ch)
    return res

total_entries = 0

for page_str, text in sorted(pages.items(), key=lambda x: int(x[0])):
    page_num = int(page_str)
    cur.execute("INSERT INTO pages (page_number, content) VALUES (?, ?)", (page_num, text))
    
    # We look for entry pattern: e.g. "២៩- " or "29- " or "២៩. "
    # Split text into entry blocks by entry number pattern at the start of a line or text segment
    # Regex matching Khmer/Western digits followed by hyphen or dot
    entry_splits = re.split(r'(\n|^)([\u17E0-\u17E90-9]+\s*[\-\–\.])', text)
    
    # Process blocks
    if len(entry_splits) > 2:
        i = 1
        while i < len(entry_splits) - 1:
            num_prefix = entry_splits[i+1].strip()
            num_clean = to_western_num(re.sub(r'[^\u17E0-\u17E90-9]', '', num_prefix))
            block_text = entry_splits[i+2] if i+2 < len(entry_splits) else ""
            i += 3
            
            lines = [l.strip() for l in block_text.split('\n') if l.strip()]
            if not lines:
                continue
                
            khmer_term = lines[0]
            english_term = ""
            french_term = ""
            definition_lines = []
            
            for line in lines[1:]:
                # Check for English term indicator (H. or អង់. or English text in parentheses or standing alone)
                if not english_term and (re.search(r'(?:H\.|អង់\.|Eng\.|E\.)\s*(.+)', line, re.IGNORECASE) or (re.search(r'[A-Za-z]', line) and not re.search(r'(?:réseau|imprimante|prévisualiser|enregistrer|menu|disponibilité|supprimer|note|propriété|décryptage)', line, re.IGNORECASE))):
                    eng_m = re.search(r'(?:H\.|អង់\.|Eng\.|E\.)?\s*([A-Za-z0-9\s\-\_\.\(\)\,\/\:\;]+)', line)
                    if eng_m:
                        english_term = eng_m.group(1).strip()
                # Check for French term indicator (i. or បារ. or Fr.)
                elif not french_term and re.search(r'(?:i\.|បារ\.|Fr\.|Q1\.|mi\.|G\.)\s*(.+)', line, re.IGNORECASE):
                    fr_m = re.search(r'(?:i\.|បារ\.|Fr\.|Q1\.|mi\.|G\.)?\s*(.+)', line)
                    if fr_m:
                        french_term = fr_m.group(1).strip()
                else:
                    definition_lines.append(line)
            
            definition = " ".join(definition_lines).strip()
            
            cur.execute("""
                INSERT INTO dictionary_entries (entry_number, khmer_term, english_term, french_term, definition, page_number, raw_block)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (num_clean, khmer_term, english_term, french_term, definition, page_num, block_text.strip()))
            
            entry_id = cur.lastrowid
            cur.execute("""
                INSERT INTO dictionary_fts (entry_id, page_number, khmer_term, english_term, french_term, definition)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (entry_id, page_num, khmer_term, english_term, french_term, definition))
            
            total_entries += 1

conn.commit()
conn.close()

print(f"Successfully structured and indexed {total_entries} dictionary entries into SQLite!")
