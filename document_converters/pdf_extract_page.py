import sys
import os
import argparse
from pypdf import PdfReader, PdfWriter

def parse_pages(page_str, total_pages):
    """
    Parses a string like '1,3,5-7' into a sorted list of zero-indexed page numbers.
    """
    pages = set()
    parts = page_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            start = int(start)
            end = int(end)
            for p in range(start, end + 1):
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p - 1)
    return sorted(list(pages))

def extract_pages(input_pdf, pages_str, output_pdf=None):
    if not os.path.exists(input_pdf):
        print(f"Error: File '{input_pdf}' not found.")
        return

    try:
        reader = PdfReader(input_pdf)
        total_pages = len(reader.pages)
        if total_pages == 0:
            print("Error: The PDF has no pages.")
            return

        pages_to_extract = parse_pages(pages_str, total_pages) if pages_str else [0]
        
        if not pages_to_extract:
            print("Error: No valid pages specified for extraction.")
            return

        if not output_pdf:
            safe_pages_str = (pages_str or '1').replace(',', '_').replace('-', 'to')
            output_pdf = os.path.splitext(input_pdf)[0] + f"_pages_{safe_pages_str}.pdf"
            
        writer = PdfWriter()
        for p in pages_to_extract:
            writer.add_page(reader.pages[p])
        
        with open(output_pdf, "wb") as output_file:
            writer.write(output_file)
            
        print(f"Success! Pages {', '.join(str(p+1) for p in pages_to_extract)} extracted and saved to:\n{output_pdf}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract specific pages from a PDF.")
    parser.add_argument("input_pdf", help="Path to the input PDF file.")
    parser.add_argument("-p", "--pages", default="1", help="Pages to extract (e.g., '1', '1,3,5', '2-4,6'). Default is '1'.")
    parser.add_argument("-o", "--output", help="Optional output PDF file path.")
    
    args = parser.parse_args()
    extract_pages(args.input_pdf, args.pages, args.output)
