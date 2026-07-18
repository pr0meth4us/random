import os
from pypdf import PdfReader, PdfWriter, Transformation

def merge_and_scale_scanned_pages():
    directory = "bro"
    final_dir = os.path.join(directory, "final")
    os.makedirs(final_dir, exist_ok=True)
    
    scanned_file = os.path.join(directory, "scanned_all_pages.pdf")
    mapping_file = os.path.join(directory, "merge_mapping.txt")
    
    if not os.path.exists(scanned_file):
        print(f"Error: Could not find '{scanned_file}'.")
        return
        
    scanned_reader = PdfReader(scanned_file)
    
    with open(mapping_file, "r") as f:
        lines = f.readlines()
        
    for scan_index, line in enumerate(lines):
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
        
        orig_page = original_reader.pages[target_page_index]
        orig_width = float(orig_page.mediabox.width)
        orig_height = float(orig_page.mediabox.height)
        
        scan_page = scanned_reader.pages[scan_index]
        scan_width = float(scan_page.mediabox.width)
        scan_height = float(scan_page.mediabox.height)
        
        # Scale the scanned page to match original size
        sx = orig_width / scan_width
        sy = orig_height / scan_height
        
        op = Transformation().scale(sx, sy)
        scan_page.add_transformation(op)
        scan_page.mediabox.upper_right = (orig_width, orig_height)
        
        for i in range(len(original_reader.pages)):
            if i == target_page_index:
                writer.add_page(scan_page)
            else:
                writer.add_page(original_reader.pages[i])
                
        # Format the new filename
        # Remove " copy" or "copy"
        clean_name = filename.replace(" copy", "").replace("copy", "")
        clean_name = clean_name.replace("_final", "")
        
        final_filename = os.path.join(final_dir, clean_name)
        with open(final_filename, "wb") as out_f:
            writer.write(out_f)
            
        print(f"Successfully scaled and replaced page {target_page_index + 1} in '{clean_name}'")

if __name__ == "__main__":
    merge_and_scale_scanned_pages()
