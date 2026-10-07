import fitz
import sys

def format_presentation(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    out_doc = fitz.open()
    
    if len(doc) == 0:
        print("Empty PDF")
        return

    # Page 1: Landscape full cover page
    out_doc.insert_pdf(doc, from_page=0, to_page=0)
    
    # Page 2+: Stacked vertically
    for i in range(1, len(doc), 2):
        p1 = doc[i]
        p2 = doc[i+1] if i+1 < len(doc) else None
        
        # Original slide width/height
        w = p1.rect.width
        h = p1.rect.height
        
        # New page is width=w, height=2h (portrait)
        new_page = out_doc.new_page(width=w, height=h*2)
        
        # Draw p1 on top half
        new_page.show_pdf_page(fitz.Rect(0, 0, w, h), doc, p1.number)
        
        # Draw p2 on bottom half
        if p2:
            new_page.show_pdf_page(fitz.Rect(0, h, w, h*2), doc, p2.number)
            
    out_doc.save(output_pdf)
    print("Formatted PDF saved to", output_pdf)

if __name__ == "__main__":
    format_presentation(sys.argv[1], sys.argv[2])
