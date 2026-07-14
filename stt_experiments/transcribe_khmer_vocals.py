import os
import sys
import time
import subprocess
from pathlib import Path
from google import genai
from dotenv import load_dotenv

def get_gemini_client():
    # Load API key from the known .env path used in Bifrost/EGD Platform
    env_path = "/Users/nicksng/code/egd platform/.env"
    load_dotenv(env_path)
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        print(f"Error: GEMINI_API_KEY not found in {env_path}")
        sys.exit(1)

    return genai.Client(api_key=api_key)

def isolate_and_resample_vocals(input_file: str) -> str:
    input_path = Path(input_file).resolve()
    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        sys.exit(1)
        
    print(f"\n--- Step 1: Isolating vocals using Demucs ---")
    out_dir = input_path.parent / "separated"
    print(f"Running Demucs on {input_path.name}...")
    subprocess.run(["demucs", "-n", "htdemucs", str(input_path), "-o", str(out_dir)], check=True)
    
    # Demucs outputs to <out_dir>/htdemucs/<basename>/vocals.wav
    basename = input_path.stem
    vocals_path = out_dir / "htdemucs" / basename / "vocals.wav"
    
    if not vocals_path.exists():
        print(f"Error: Demucs failed to produce {vocals_path}")
        sys.exit(1)
        
    print(f"\n--- Step 2: Resampling to 16kHz mono using FFmpeg ---")
    final_audio = out_dir / f"{basename}_vocals_16k.wav"
    # Overwrite if exists (-y)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(vocals_path),
        "-ar", "16000", "-ac", "1",
        str(final_audio)
    ], check=True)
    
    return str(final_audio)

def transcribe_audio(client: genai.Client, audio_path: str):
    print(f"\n--- Step 3: Uploading {Path(audio_path).name} to Gemini File API ---")
    audio_file = client.files.upload(file=audio_path)
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

    # Use gemini-1.5-flash since the 2.x models hit quota issues (as documented in random_stt_agents.md)
    model_name = "gemini-1.5-flash" 
    print(f"\n--- Step 4: Transcribing with {model_name} ---")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[audio_file, prompt]
            )
            print("\n================== TRANSCRIPTION ==================\n")
            print(response.text)
            print("\n===================================================\n")
            
            # Save the transcription
            out_txt = Path(audio_path).with_name(f"{Path(audio_path).stem}_transcription.txt")
            with open(out_txt, "w", encoding="utf-8") as f:
                f.write(response.text or "NO TEXT")
            print(f"Transcription saved to: {out_txt}")
            break
        except Exception as e:
            print(f"Attempt {attempt+1} FAILED: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)

    print("\nCleaning up uploaded file from Gemini servers...")
    client.files.delete(name=audio_file.name)
    print("Done.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe_khmer_vocals.py <path_to_audio_or_video_file>")
        sys.exit(1)
        
    input_media = sys.argv[1]
    client = get_gemini_client()
    
    # Run the pipeline
    processed_audio_path = isolate_and_resample_vocals(input_media)
    transcribe_audio(client, processed_audio_path)
