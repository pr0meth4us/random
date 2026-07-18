import os
from pypdf import PdfReader, PdfWriter

def extract_signing_pages():
    directory = "."
    for filename in os.listdir(directory):
        if "copy" in filename and filename.endswith(".pdf") and not filename.endswith("_signing_page.pdf") and not filename.endswith("_signed_full.pdf"):
            reader = PdfReader(filename)
            
            target_page_index = -1
            # Search for the specific Khmer keywords identifying the signature block
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and ("មុខតំែណង" in text and "ហតថេលខ" in text):
                    target_page_index = i
                    break
            
            if target_page_index == -1:
                print(f"Could not find signature page in {filename}")
                continue
                
            # Extract the identified page
            writer = PdfWriter()
            writer.add_page(reader.pages[target_page_index])
            
            out_filename = filename.replace(".pdf", "_signing_page.pdf")
            with open(out_filename, "wb") as f:
                writer.write(f)
            
            print(f"Extracted page {target_page_index + 1} from '{filename}' to '{out_filename}'")

if __name__ == "__main__":
    extract_signing_pages()
