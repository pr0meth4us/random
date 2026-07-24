import os
import sys
import time
import shutil
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

def transcribe_chunked(audio_path: str, chunk_time: int = 1800):
    client = get_gemini_client()
    input_path = Path(audio_path).resolve()
    
    # 1. Create chunks directory
    chunks_dir = input_path.parent / f"{input_path.stem}_chunks"
    chunks_dir.mkdir(exist_ok=True)
    
    print(f"\n--- Step 1: Chunking {input_path.name} into {chunk_time}s 16kHz Mono WAVs ---")
    chunk_pattern = chunks_dir / "chunk_%03d.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-f", "segment", "-segment_time", str(chunk_time),
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(chunk_pattern)
    ], check=True)

    # 2. Get list of generated chunks
    chunks = sorted(list(chunks_dir.glob("chunk_*.wav")))
    if not chunks:
        print("Error: No chunks were created.")
        sys.exit(1)

    print(f"Created {len(chunks)} chunks.")

    out_txt = input_path.with_name(f"{input_path.stem}_chunked_transcription.txt")
    # Clear output file if it exists
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("")

    prompt = (
        "You are an expert transcriber of the Khmer language. "
        "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
        "Do not translate it to English. "
        "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
        "Only output the transcribed text."
    )
    model_name = "gemini-flash-latest"

    # 3. Process each chunk
    for i, chunk_path in enumerate(chunks):
        print(f"\n--- Processing Chunk {i+1}/{len(chunks)}: {chunk_path.name} ---")
        
        print(f"Uploading...")
        audio_file = client.files.upload(file=str(chunk_path))
        
        print("Waiting for audio processing to complete...")
        while True:
            file_info = client.files.get(name=audio_file.name)
            if file_info.state.name == "ACTIVE":
                break
            elif file_info.state.name == "FAILED":
                print(f"Audio processing failed for {chunk_path.name} on Gemini's servers.")
                sys.exit(1)
            time.sleep(2)

        print("Transcribing...")
        max_retries = 3
        transcribed_text = ""
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[audio_file, prompt]
                )
                
                if not response.text:
                    print(f"Attempt {attempt+1} FAILED: Gemini returned an empty response.")
                    raise ValueError("Empty response text")

                transcribed_text = response.text
                break
            except Exception as e:
                print(f"Attempt {attempt+1} FAILED: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)

        if not transcribed_text:
            print(f"Failed to transcribe {chunk_path.name} after {max_retries} attempts.")
        else:
            # Append to final text file
            with open(out_txt, "a", encoding="utf-8") as f:
                f.write(f"\n\n--- Chunk {i+1} ---\n\n")
                f.write(transcribed_text)
            print(f"✅ Chunk {i+1} saved.")

        # Delete from Gemini API immediately to save quota
        try:
            client.files.delete(name=audio_file.name)
        except Exception as e:
            print(f"Cleanup warning for API file {audio_file.name}: {e}")

    # 4. Clean up local chunks directory
    print("\nCleaning up temporary local chunks...")
    shutil.rmtree(chunks_dir)
    print(f"\n🎉 FULL TRANSCRIPTION SAVED TO: {out_txt}")

if __name__ == "__main__":
    # Force stdout/stderr to be unbuffered so we can see print statements in real-time
    sys.stdout.reconfigure(line_buffering=True)
    
    if len(sys.argv) < 2:
        print("Usage: python transcribe_chunked.py <file>")
        sys.exit(1)
    transcribe_chunked(sys.argv[1])
