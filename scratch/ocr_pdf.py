import os
import sys
import time
from pathlib import Path
import shutil
from google import genai
from dotenv import load_dotenv

def get_gemini_client():
    env_path = "/Users/nicksng/code/egd platform/.env"
    load_dotenv(env_path)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print(f"Error: GEMINI_API_KEY not found in {env_path}")
        sys.exit(1)
    return genai.Client(api_key=api_key)

def ocr_pdf(pdf_path: str):
    client = get_gemini_client()
    input_path = Path(pdf_path).resolve()
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        sys.exit(1)

    print(f"\n--- Step 1: Uploading {input_path.name} to Gemini File API ---")
    
    # Workaround for UnicodeEncodeError in httpx due to Khmer filename
    temp_pdf = input_path.with_name("temp_upload_ascii.pdf")
    shutil.copy2(input_path, temp_pdf)
    
    try:
        file_obj = client.files.upload(file=str(temp_pdf))
    finally:
        os.remove(temp_pdf)
        
    print(f"File uploaded successfully. URI: {file_obj.uri}")

    print("Waiting for file processing to complete...")
    while True:
        file_info = client.files.get(name=file_obj.name)
        if file_info.state.name == "ACTIVE":
            print("File is ready!")
            break
        elif file_info.state.name == "FAILED":
            print("File processing failed on Gemini's servers.")
            sys.exit(1)
        time.sleep(2)

    prompt = (
        "Extract and transcribe all the text from this document page by page. "
        "Maintain the logical order and format it clearly. If there is Khmer text, transcribe it exactly as written. "
        "Do not summarize, just perform OCR."
    )

    model_name = "gemini-flash-latest"
    print(f"\n--- Step 2: Extracting text with {model_name} ---")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[file_obj, prompt]
            )
            
            if not response.text:
                print(f"Attempt {attempt+1} FAILED: Gemini returned an empty response.")
                raise ValueError("Empty response text")

            out_txt = input_path.with_name(f"{input_path.stem}_ocr_transcription.txt")
            with open(out_txt, "w", encoding="utf-8") as f:
                f.write(response.text)
            print(f"✅ Transcription saved to: {out_txt}")
            break
        except Exception as e:
            print(f"Attempt {attempt+1} FAILED: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)

    print("\nCleaning up temporary files from Gemini...")
    try:
        client.files.delete(name=file_obj.name)
    except Exception as e:
        print(f"Cleanup warning: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ocr_pdf.py <file.pdf>")
        sys.exit(1)
    ocr_pdf(sys.argv[1])
