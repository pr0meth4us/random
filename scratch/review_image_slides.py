import os
import glob
import re
from PIL import Image
from google import genai

# Setup API Key
os.environ["GEMINI_API_KEY"] = "AIzaSyAvXMWisO5U8MhRgRmyVX9G5JkNDVOY-Yg"
client = genai.Client()

def review_image_slides(image_dir, output_path):
    # Find all slide images
    image_paths = sorted(glob.glob(os.path.join(image_dir, "slide_*.png")))
    print(f"Found {len(image_paths)} slide images to review.")
    
    # Check already processed slides
    processed_slides = set()
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            for num in re.findall(r"--- Slide (\d+) ---", content):
                processed_slides.add(int(num))
    
    print(f"Already processed slides: {sorted(list(processed_slides))}")
    
    # Open in append mode
    mode = "a" if os.path.exists(output_path) else "w"
    with open(output_path, mode, encoding="utf-8") as out_f:
        if mode == "w":
            out_f.write("=== IMAGE-ONLY SLIDES REVIEW ===\n\n")
        
        for path in image_paths:
            # Extract slide number from filename
            match = re.search(r"slide_(\d+)\.png", path)
            if not match:
                continue
            slide_num = int(match.group(1))
            
            if slide_num in processed_slides:
                print(f"Skipping Slide {slide_num} (already processed)")
                continue
            
            print(f"Analyzing Slide {slide_num}...")
            
            prompt = (
                "You are an expert editor and presentation reviewer.\n"
                "Analyze the attached slide image. It is in Khmer and/or English.\n"
                "Perform the following tasks:\n"
                "1. Provide a brief 1-sentence summary of the slide's topic.\n"
                "2. Check for any spelling mistakes, typos, grammatical errors, or awkward formatting (e.g. text overlaps, cut-off sentences, bad line breaks, or font size inconsistencies) in both Khmer and English.\n"
                "3. If any errors are found, list:\n"
                "   - Incorrect text\n"
                "   - Corrected text\n"
                "   - Explanation (in English)\n"
                "If no errors are found, write 'No errors found.'\n"
            )
            
            try:
                img = Image.open(path)
                # Convert RGBA to RGB if necessary (Gemini prefers RGB or PNG)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                    
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[img, prompt]
                )
                
                out_f.write(f"--- Slide {slide_num} ---\n")
                out_f.write(response.text)
                out_f.write("\n\n" + "="*50 + "\n\n")
                out_f.flush()
                
            except Exception as e:
                print(f"Error analyzing slide {slide_num}: {e}")
                out_f.write(f"--- Slide {slide_num} ERROR: {e} ---\n\n")
                out_f.flush()
                
    print(f"Review completed. Results saved to {output_path}")

if __name__ == "__main__":
    image_dir = "/Users/nicksng/code/random/scratch/slide_images"
    output_path = "/Users/nicksng/code/random/scratch/image_review_results.txt"
    review_image_slides(image_dir, output_path)
