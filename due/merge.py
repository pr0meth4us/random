import os
from pypdf import PdfReader, PdfWriter

def merge_signed_pages():
    directory = "."
    for filename in os.listdir(directory):
        if "copy" in filename and filename.endswith(".pdf") and not filename.endswith("_signing_page.pdf") and not filename.endswith("_signed.pdf") and not filename.endswith("_final.pdf"):
            signed_filename = filename.replace(".pdf", "_signed.pdf")
            final_filename = filename.replace(".pdf", "_final.pdf")
            
            if os.path.exists(signed_filename):
                original_reader = PdfReader(filename)
                signed_reader = PdfReader(signed_filename)
                
                if len(signed_reader.pages) == 0:
                    print(f"Warning: {signed_filename} has no pages.")
                    continue
                
                # Find the target page index in original file
                target_page_index = -1
                for i, page in enumerate(original_reader.pages):
                    text = page.extract_text()
                    if text and ("មុខតំែណង" in text and "ហតថេលខ" in text):
                        target_page_index = i
                        break
                
                if target_page_index == -1:
                    print(f"Could not find signature page in {filename}")
                    continue
                
                writer = PdfWriter()
                
                # Add pages, replacing the target page with the signed scan
                for i in range(len(original_reader.pages)):
                    if i == target_page_index:
                        writer.add_page(signed_reader.pages[0])
                    else:
                        writer.add_page(original_reader.pages[i])
                
                with open(final_filename, "wb") as f:
                    writer.write(f)
                    
                print(f"Successfully merged signed page into '{final_filename}' (replaced page {target_page_index + 1})")
            else:
                pass # print(f"Waiting for '{signed_filename}'")

if __name__ == "__main__":
    merge_signed_pages()
