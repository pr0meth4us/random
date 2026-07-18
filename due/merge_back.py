import os
from pypdf import PdfReader, PdfWriter

import sys

def merge_scanned_pages():
    directory = sys.argv[1] if len(sys.argv) > 1 else "ok"
    scanned_file = os.path.join(directory, "scanned_all_pages.pdf")
    mapping_file = os.path.join(directory, "merge_mapping.txt")
    
    if not os.path.exists(scanned_file):
        print(f"Error: Could not find '{scanned_file}'. Please place your scanned PDF there and name it exactly 'scanned_all_pages.pdf'.")
        return
        
    if not os.path.exists(mapping_file):
        print(f"Error: Could not find mapping file '{mapping_file}'. This should have been created by the extraction script.")
        return
        
    scanned_reader = PdfReader(scanned_file)
    
    with open(mapping_file, "r") as f:
        lines = f.readlines()
        
    if len(scanned_reader.pages) != len(lines):
        print(f"Warning: The scanned PDF has {len(scanned_reader.pages)} pages, but we extracted {len(lines)} pages.")
        # Proceed anyway, we'll just map one by one
        
    for scan_index, line in enumerate(lines):
        if scan_index >= len(scanned_reader.pages):
            print(f"Not enough pages in the scanned PDF for '{filename}'.")
            break
            
        line = line.strip()
        if not line: continue
        
        filename, target_page_index_str = line.split("|")
        target_page_index = int(target_page_index_str)
        
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            print(f"Error: Original file '{filepath}' not found.")
            continue
            
        original_reader = PdfReader(filepath)
        writer = PdfWriter()
        
        for i in range(len(original_reader.pages)):
            if i == target_page_index:
                writer.add_page(scanned_reader.pages[scan_index])
            else:
                writer.add_page(original_reader.pages[i])
                
        final_filename = os.path.join(directory, filename.replace(".pdf", "_final.pdf"))
        with open(final_filename, "wb") as out_f:
            writer.write(out_f)
            
        print(f"Successfully replaced page {target_page_index + 1} in '{filename}' and saved to '{os.path.basename(final_filename)}'")

if __name__ == "__main__":
    merge_scanned_pages()
