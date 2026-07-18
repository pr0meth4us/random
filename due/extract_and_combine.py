import os
from pypdf import PdfReader, PdfWriter

import sys

def extract_and_combine_signing_pages():
    directory = sys.argv[1] if len(sys.argv) > 1 else "ok"
    combined_writer = PdfWriter()
    
    # Sort files to ensure a predictable order for merging later
    files = sorted([f for f in os.listdir(directory) if f.endswith(".pdf") and f != "all_signing_pages_to_print.pdf" and not f.endswith("_final.pdf")])
    
    extracted_count = 0
    
    with open(os.path.join(directory, "merge_mapping.txt"), "w") as mapping_file:
        for filename in files:
            filepath = os.path.join(directory, filename)
            reader = PdfReader(filepath)
            
            target_page_index = -1
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and ("មុខតំែណង" in text and "ហតថេលខ" in text):
                    target_page_index = i
                    break
            
            if target_page_index == -1:
                print(f"Could not find signature page in {filename}")
                continue
                
            combined_writer.add_page(reader.pages[target_page_index])
            extracted_count += 1
            print(f"Extracted page {target_page_index + 1} from '{filename}'")
            
            # Save the mapping so we know which page index belongs to which file
            mapping_file.write(f"{filename}|{target_page_index}\n")
            
    out_filename = os.path.join(directory, "all_signing_pages_to_print.pdf")
    with open(out_filename, "wb") as f:
        combined_writer.write(f)
        
    print(f"\nSuccessfully combined {extracted_count} signing pages into '{out_filename}'")

if __name__ == "__main__":
    extract_and_combine_signing_pages()
