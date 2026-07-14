import re
import os

text_file = "scratch/text_review_results.txt"
image_file = "scratch/image_review_results.txt"

def parse_text_results(filepath):
    if not os.path.exists(filepath):
        return {}
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split by Slide header
    slides = re.split(r"\*\*Slide (\d+)\*\*", content)
    results = {}
    
    # The first element is before any slide header
    for i in range(1, len(slides), 2):
        slide_num = int(slides[i])
        slide_content = slides[i+1].strip()
        
        # Parse individual errors
        errors = []
        # Find matches for:
        # - **Original (Incorrect) text:** ...
        # - **Corrected text:** ...
        # - **Reason for correction:** ...
        pattern = r"-\s*\*\*Original\s*\(Incorrect\)\s*text:\*\*\s*(.*?)\n-\s*\*\*Corrected\s*text:\*\*\s*(.*?)\n-\s*\*\*Reason\s*for\s*correction:\*\*\s*(.*?)(?=\n-|\n\n|\Z)"
        matches = re.findall(pattern, slide_content, re.DOTALL)
        for original, corrected, reason in matches:
            errors.append({
                "type": "Text Shape",
                "original": original.strip(),
                "corrected": corrected.strip(),
                "reason": reason.strip()
            })
            
        # Also handle standard format:
        # 1. **Original:** ...
        #    - **Corrected:** ...
        #    - **Reason:** ...
        pattern2 = r"\d+\.\s*\*\*Original:\*\*\s*(.*?)\n\s*-\s*\*\*Corrected:\*\*\s*(.*?)\n\s*-\s*\*\*Reason:\*\*\s*(.*?)(?=\n\d+\.|\n\n|\Z)"
        matches2 = re.findall(pattern2, slide_content, re.DOTALL)
        for original, corrected, reason in matches2:
            errors.append({
                "type": "Text Shape",
                "original": original.strip(),
                "corrected": corrected.strip(),
                "reason": reason.strip()
            })
            
        if errors:
            results[slide_num] = errors
            
    return results

def parse_image_results(filepath):
    if not os.path.exists(filepath):
        return {}
        
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    slides = re.split(r"--- Slide (\d+) ---", content)
    results = {}
    
    for i in range(1, len(slides), 2):
        slide_num = int(slides[i])
        slide_content = slides[i+1].strip()
        
        # Check if "No errors found" or "No errors were found" is in the slide content
        if "No errors found" in slide_content or "No errors were found" in slide_content:
            continue
            
        # Parse bullet points for errors
        errors = []
        
        # Find standard format:
        # *   **Incorrect text:** ...
        #     *   **Corrected text:** ...
        #     *   **Explanation:** ...
        pattern = r"\*\s*\*\*Incorrect\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\s*\*\*Corrected\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\s*\*\*Explanation:\*\*\s*(.*?)(?=\n\*|\n\n|\Z)"
        matches = re.findall(pattern, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches:
            errors.append({
                "type": "Image Text",
                "original": incorrect.strip(),
                "corrected": corrected.strip(),
                "reason": explanation.strip()
            })
            
        # Alternative format:
        # *   **Incorrect formatting:** ...
        #     *   **Corrected formatting:** ...
        #     *   **Explanation:** ...
        pattern_fmt = r"\*\s*\*\*Incorrect\s*formatting(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\s*\*\*Corrected\s*formatting(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\s*\*\*Explanation:\*\*\s*(.*?)(?=\n\*|\n\n|\Z)"
        matches_fmt = re.findall(pattern_fmt, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches_fmt:
            errors.append({
                "type": "Image Formatting",
                "original": incorrect.strip(),
                "corrected": corrected.strip(),
                "reason": explanation.strip()
            })
            
        # Alternative format:
        # -   **Incorrect text:** ...
        #     **Corrected text:** ...
        #     **Explanation:** ...
        pattern2 = r"-\s*\*\*Incorrect\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\*Corrected\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\*Explanation:\*\*\s*(.*?)(?=\n-|\n\n|\Z)"
        matches2 = re.findall(pattern2, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches2:
            errors.append({
                "type": "Image Text",
                "original": incorrect.strip(),
                "corrected": corrected.strip(),
                "reason": explanation.strip()
            })
            
        # Another format:
        # *   **Incorrect text:** ...
        #     - **Corrected text:** ...
        #     - **Explanation:** ...
        pattern3 = r"\*\s*\*\*Incorrect\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*-\s*\*\*Corrected\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*-\s*\*\*Explanation:\*\*\s*(.*?)(?=\n\*|\n\n|\Z)"
        matches3 = re.findall(pattern3, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches3:
            errors.append({
                "type": "Image Text",
                "original": incorrect.strip(),
                "corrected": corrected.strip(),
                "reason": explanation.strip()
            })
            
        # Another format:
        # **Incorrect text (Language):** ...
        # **Corrected text (Language):** ...
        # **Explanation:** ...
        pattern4 = r"\*\*\s*Incorrect\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\*\s*Corrected\s*text(?:\s*\(.*?\))?:\*\*\s*(.*?)\n\s*\*\*\s*Explanation:\*\*\s*(.*?)(?=\n\*\*|\n\n|\Z)"
        matches4 = re.findall(pattern4, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches4:
            errors.append({
                "type": "Image Text",
                "original": incorrect.strip(),
                "corrected": corrected.strip(),
                "reason": explanation.strip()
            })

        # Check for individual error subheadings:
        # *   **Error X: ...**
        #     *   **Incorrect text:** ...
        #     *   **Corrected text:** ...
        #     *   **Explanation:** ...
        pattern5 = r"\*\s*\*\*Incorrect\s*text:\*\*\s*(.*?)\n\s*\*\s*\*\*Corrected\s*text:\*\*\s*(.*?)\n\s*\*\s*\*\*Explanation:\*\*\s*(.*?)(?=\n\s*\*|\n\n|\Z)"
        # Note: If pattern5 finds matches, make sure they aren't duplicate
        matches5 = re.findall(pattern5, slide_content, re.DOTALL)
        for incorrect, corrected, explanation in matches5:
            # check if duplicate
            exists = False
            for err in errors:
                if err["original"] == incorrect.strip():
                    exists = True
                    break
            if not exists:
                errors.append({
                    "type": "Image Text",
                    "original": incorrect.strip(),
                    "corrected": corrected.strip(),
                    "reason": explanation.strip()
                })
        
        # If we didn't extract any errors but slide content has text, let's just log it as general review
        if not errors and len(slide_content) > 100 and "No errors found" not in slide_content:
            # Try to grab the errors section or summarize
            errors.append({
                "type": "General Image Review",
                "original": "(See detailed description)",
                "corrected": "(See detailed description)",
                "reason": slide_content
            })
            
        if errors:
            # Merge if already exists from double run
            if slide_num in results:
                results[slide_num].extend(errors)
            else:
                results[slide_num] = errors
                
    return results

text_errors = parse_text_results(text_file)
image_errors = parse_image_results(image_file)

# Combine results
all_slides = sorted(list(set(list(text_errors.keys()) + list(image_errors.keys()))))

print(f"Total slides with errors: {len(all_slides)}")
print(f"Text slides with errors: {len(text_errors)}")
print(f"Image slides with errors: {len(image_errors)}")

with open("scratch/synthesis_summary.txt", "w", encoding="utf-8") as out:
    for slide_num in all_slides:
        out.write(f"=== Slide {slide_num:03d} ===\n")
        
        if slide_num in text_errors:
            for err in text_errors[slide_num]:
                out.write(f"[{err['type']}]\n")
                out.write(f"  - Original:  \"{err['original']}\"\n")
                out.write(f"  - Corrected: \"{err['corrected']}\"\n")
                out.write(f"  - Reason:    {err['reason']}\n")
                
        if slide_num in image_errors:
            for err in image_errors[slide_num]:
                out.write(f"[{err['type']}]\n")
                out.write(f"  - Original:  \"{err['original']}\"\n")
                out.write(f"  - Corrected: \"{err['corrected']}\"\n")
                out.write(f"  - Reason:    {err['reason']}\n")
        out.write("\n")
