import os
import sys
import time
from pathlib import Path
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

def transcribe_pptx(pptx_path: str):
    client = get_gemini_client()
    input_path = Path(pptx_path).resolve()
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        sys.exit(1)

    print(f"\n--- Step 1: Uploading {input_path.name} to Gemini File API ---")
    file_obj = client.files.upload(file=str(input_path))
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
        "Extract and transcribe all the text from this presentation slide by slide. "
        "Maintain the logical order and format it clearly. If there is Khmer text, transcribe it exactly."
    )

    model_name = "gemini-1.5-pro" # 1.5-pro is usually better at complex document understanding, but let's stick to flash-latest if pro is sunset
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

            out_txt = input_path.with_name(f"{input_path.stem}_transcription.txt")
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
        print("Usage: python transcribe_pptx.py <file.pptx>")
        sys.exit(1)
    transcribe_pptx(sys.argv[1])
