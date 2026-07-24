#!/usr/bin/env python3
"""
CLI Query Utility for National Council of Khmer Language (NCKL) Technology Glossary
(ក្រុមប្រឹក្សាជាតិភាសាខ្មែរ - ពាក្យបច្ចេកវិទ្យា)
"""
import sys
import sqlite3
import os

db_path = '/Users/nicksng/code/random/nckl_ocr_output/nckl_tech_terms.db'

def search(query):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'.")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    print(f"🔍 Searching NCKL Tech Terms index for: '{query}'...\n")

    # Query structured entries table
    cur.execute("""
        SELECT entry_number, khmer_term, english_term, french_term, definition, page_number
        FROM dictionary_entries
        WHERE english_term LIKE ? OR khmer_term LIKE ? OR french_term LIKE ? OR definition LIKE ?
        ORDER BY page_number ASC
        LIMIT 25
    """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))

    entries = cur.fetchall()

    if entries:
        print(f"Found {len(entries)} matching term entries:\n")
        print("=" * 100)
        for e in entries:
            num, khmer, eng, fr, defn, page = e
            print(f"📌 Entry #{num} | Page {page}")
            print(f"   🇰🇭 Khmer Term   : {khmer}")
            if eng:
                print(f"   🇬🇧 English Term : {eng}")
            if fr:
                print(f"   🇫🇷 French Term  : {fr}")
            if defn:
                print(f"   📖 Definition   : {defn}")
            print("-" * 100)
    else:
        # Fallback to full page search
        cur.execute("""
            SELECT page_number, content
            FROM pages
            WHERE content LIKE ?
            LIMIT 5
        """, (f'%{query}%',))
        pages = cur.fetchall()
        if pages:
            print(f"No specific entry matched, but found term on {len(pages)} pages:\n")
            for p in pages:
                print(f"📄 --- Page {p[0]} ---")
                matching_lines = [l for l in p[1].split('\n') if query.lower() in l.lower()]
                for ml in matching_lines[:5]:
                    print(f"   • {ml}")
        else:
            print("❌ No matching terms or text found.")

    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 query_terms.py <search_keyword>")
        print("Example: python3 query_terms.py network")
        print("Example: python3 query_terms.py កុំព្យូទ័រ")
        sys.exit(1)
    search(" ".join(sys.argv[1:]))
