import re

def summarize_output(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    slides = content.split("--- Slide ")
    summary = []
    
    # The first split element is metadata before slide 1
    for slide_data in slides[1:]:
        lines = slide_data.split("\n")
        slide_num_match = re.match(r"^(\d+)", lines[0])
        if not slide_num_match:
            continue
        slide_num = int(slide_num_match.group(1))
        
        text_lines = []
        in_text = False
        for line in lines:
            if "Extracted Text:" in line:
                in_text = True
                continue
            elif in_text and line.strip().startswith("-"):
                # Clean bullet formatting
                txt = line.strip().lstrip("-").strip()
                if txt:
                    text_lines.append(txt)
            elif in_text and not line.strip().startswith("-") and line.strip() != "":
                # We hit something else (like Notes or empty line)
                break
                
        # Get first 3 non-empty text elements
        first_texts = text_lines[:4]
        summary.append((slide_num, first_texts))
        
    for num, texts in summary:
        text_str = " | ".join(texts) if texts else "[No Text]"
        print(f"Slide {num:03d}: {text_str[:120]}")

if __name__ == "__main__":
    summarize_output("/Users/nicksng/code/random/scratch/inspect_output.txt")
