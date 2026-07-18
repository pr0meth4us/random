import os
import sys
import time
import subprocess
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

def transcribe_direct(audio_path: str):
    client = get_gemini_client()
    input_path = Path(audio_path).resolve()
    
    print(f"\n--- Step 1: Converting {input_path.name} to 16kHz Mono WAV ---")
    wav_path = input_path.with_name(f"{input_path.stem}_16k.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-ar", "16000", "-ac", "1",
        str(wav_path)
    ], check=True)

    print(f"\n--- Step 2: Uploading {wav_path.name} to Gemini File API ---")
    audio_file = client.files.upload(file=str(wav_path))
    print(f"File uploaded successfully. URI: {audio_file.uri}")

    print("Waiting for audio processing to complete...")
    while True:
        file_info = client.files.get(name=audio_file.name)
        if file_info.state.name == "ACTIVE":
            print("Audio is ready!")
            break
        elif file_info.state.name == "FAILED":
            print("Audio processing failed on Gemini's servers.")
            sys.exit(1)
        time.sleep(2)

    prompt = (
        "You are an expert transcriber of the Khmer language. "
        "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
        "Do not translate it to English. "
        "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
        "Only output the transcribed text."
    )

    model_name = "gemini-flash-latest" 
    print(f"\n--- Step 3: Transcribing with {model_name} ---")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[audio_file, prompt]
            )
            
            # Catch empty responses (MALFORMED_RESPONSE)
            if not response.text:
                print(f"Attempt {attempt+1} FAILED: Gemini returned an empty response. (Possible safety block or decode error)")
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

    print("\nCleaning up temporary files...")
    try:
        client.files.delete(name=audio_file.name)
        os.remove(wav_path)
    except Exception as e:
        print(f"Cleanup warning: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe_direct.py <file>")
        sys.exit(1)
    transcribe_direct(sys.argv[1])
