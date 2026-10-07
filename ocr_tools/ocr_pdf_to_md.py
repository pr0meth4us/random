import os
import fitz
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import vision

def main():
    parser = argparse.ArgumentParser(description="OCR a PDF using Google Cloud Vision and save to Markdown")
    parser.add_argument('--pdf', required=True, help="Path to input PDF file")
    parser.add_argument('--out', required=True, help="Path to output markdown file")
    args = parser.parse_args()

    pdf_path = args.pdf
    md_output_path = args.out

    print(f"Opening PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"Total PDF pages: {total_pages}")

    client = vision.ImageAnnotatorClient()

    def process_page(page_idx):
        page = doc[page_idx]
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

    sorted_pages = {p: pages_data[p] for p in sorted(pages_data.keys())}

    with open(md_output_path, 'w', encoding='utf-8') as f:
        f.write(f"# OCR Transcription of {os.path.basename(pdf_path)}\n\n")
        for p_num, text in sorted_pages.items():
            f.write(f"## Page {p_num}\n\n")
            f.write(text.strip() if text else "*(No text detected)*")
            f.write("\n\n---\n\n")
            
    print(f"Saved Markdown OCR document to: {md_output_path}")

if __name__ == "__main__":
    main()
