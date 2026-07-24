import os
import json
import subprocess
from google import genai
from pathlib import Path

# Use the API key found in the workspace
GEMINI_API_KEY = "AIzaSyBuAYLKa9__PVTqNcTwNw3VCWEEBpDbdEM"
client = genai.Client(api_key=GEMINI_API_KEY)

VOICE_DIR = "/Users/nicksng/code/random/voice_messages"
OUTPUT_FILE = "/Users/nicksng/code/random/transcriptions_gemini.json"
TEMP_DIR = "/Users/nicksng/code/random/temp_processing"

def process_file(filepath):
    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]
    
    # 1. Isolate Vocals using Demucs
    demucs_out = os.path.join(TEMP_DIR, "htdemucs", name_no_ext)
    vocal_file = os.path.join(demucs_out, "vocals.wav")
    
    print(f"  [{filename}] Isolating vocals (Demucs)...")
    # Using uvx to run demucs seamlessly if not installed globally (adding numpy explicitly to avoid import errors)
    subprocess.run(["uvx", "--with", "numpy", "demucs", "-o", TEMP_DIR, "-n", "htdemucs", filepath], check=True, capture_output=True)
    
    if not os.path.exists(vocal_file):
        raise FileNotFoundError(f"Demucs failed to produce {vocal_file}")

    # 2. Resample to 16kHz mono using ffmpeg
    resampled_file = os.path.join(TEMP_DIR, f"{name_no_ext}_16k.wav")
    print(f"  [{filename}] Resampling to 16kHz mono (ffmpeg)...")
    subprocess.run(["ffmpeg", "-y", "-i", vocal_file, "-ar", "16000", "-ac", "1", resampled_file], check=True, capture_output=True)
    
    # 3. Upload via Gemini File API
    print(f"  [{filename}] Uploading to Gemini...")
    audio_file = client.files.upload(file=resampled_file)
    
    # 4. Prompt Gemini Flash Latest
    print(f"  [{filename}] Generating transcription...")
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=["Please transcribe the Khmer audio exactly as spoken. Output ONLY the transcription, with proper orthography and logical line breaks.", audio_file]
    )
    
    # Cleanup Gemini File to save space
    client.files.delete(name=audio_file.name)
    
    return response.text.strip()

def main():
    print("=== Starting Khmer STT Pipeline: Demucs + Gemini Flash ===")
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    if not os.path.exists(VOICE_DIR):
        print(f"Directory {VOICE_DIR} not found.")
        return
        
    files = [f for f in os.listdir(VOICE_DIR) if f.endswith(".ogg")]
    print(f"Found {len(files)} voice messages to transcribe.\n")
    
    transcriptions = {}
    
    for idx, filename in enumerate(files, 1):
        file_path = os.path.join(VOICE_DIR, filename)
        print(f"\n--- Processing {idx}/{len(files)}: {filename} ---")
        try:
            text = process_file(file_path)
            transcriptions[filename] = {"text": text}
            print(f"Result:\n{text}")
        except Exception as e:
            print(f"Failed processing {filename}: {e}")
            transcriptions[filename] = {"error": str(e)}
            
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(transcriptions, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ Done! Saved all transcriptions to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
