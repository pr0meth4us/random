import argparse
import sys
import io
import fitz  # PyMuPDF
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE

def convert_pdf_to_pptx(pdf_path, pptx_path, zoom=4.0):
    try:
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)
        
    prs = Presentation()
    # Remove default blank slide layout if any, we'll just use a blank layout
    blank_slide_layout = prs.slide_layouts[6] 
    
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        
        # Get page dimensions in points (1/72 inch)
        page_width_pt = page.rect.width
        page_height_pt = page.rect.height
        
        # Convert points to inches for python-pptx
        width_inches = page_width_pt / 72.0
        height_inches = page_height_pt / 72.0
        
        # If it's the first page, set the presentation dimensions
        if page_num == 0:
            prs.slide_width = Inches(width_inches)
            prs.slide_height = Inches(height_inches)
        
        # Render the page to an image (high resolution)
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        
        # Convert Pixmap to bytes
        img_bytes = pix.tobytes("png")
        img_stream = io.BytesIO(img_bytes)
        
        # Add a slide
        slide = prs.slides.add_slide(blank_slide_layout)
        
        # Add the image to the slide
        slide.shapes.add_picture(img_stream, 0, 0, width=Inches(width_inches), height=Inches(height_inches))
        
        print(f"Processed page {page_num + 1}/{len(pdf_document)}")

    # Save the PPTX
    try:
        prs.save(pptx_path)
        print(f"Successfully saved to {pptx_path}")
    except Exception as e:
        print(f"Error saving PPTX: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PDF to high-resolution PPTX (as images).")
    parser.add_argument("input_pdf", help="Path to the input PDF file")
    parser.add_argument("output_pptx", help="Path to the output PPTX file")
    parser.add_argument("--zoom", type=float, default=4.0, help="Zoom factor for image resolution (default: 4.0)")
    
    args = parser.parse_args()
    
    convert_pdf_to_pptx(args.input_pdf, args.output_pptx, zoom=args.zoom)
