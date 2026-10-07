import os
import sys
import time
import shutil
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from google import genai
from google.genai import types

def get_vertex_client(location=None):
    """Fetches credentials from Bifrost/environment and initializes Vertex AI Client.

    `location` overrides the region (Bifrost's VERTEX_AI_LOCATION, else
    asia-southeast1). Needed for models not served there: gemini-2.5-pro 404s in
    asia-southeast1 but is available in us-central1 and global.
    """
    load_dotenv()
    load_dotenv("/Users/nicksng/code/random/.env")
    
    bifrost_url = os.getenv("BIFROST_URL")
    client_id = os.getenv("BIFROST_CLIENT_ID")
    webhook_secret = os.getenv("BIFROST_WEBHOOK_SECRET")
    
    sa_json = None
    project = "khmer-ocr-496606"
    override_location = location
    location = "asia-southeast1"
    
    if bifrost_url and client_id and webhook_secret:
        try:
            res = requests.get(
                f"{bifrost_url.rstrip('/')}/api/v1/config",
                headers={"X-Client-ID": client_id, "X-Webhook-Secret": webhook_secret},
                timeout=10
            )
            if res.status_code == 200:
                data = res.json().get("data", {}).get("api_keys", {})
                sa_json = data.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
                project = data.get("VERTEX_AI_PROJECT", project)
                location = data.get("VERTEX_AI_LOCATION", location)
        except Exception as e:
            print(f"Warning: Could not fetch secrets from Bifrost: {e}")

    if sa_json:
        sa_path = "/tmp/bifrost_vertex_sa.json"
        with open(sa_path, "w", encoding="utf-8") as f:
            f.write(sa_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path

    return genai.Client(vertexai=True, project=project,
                        location=override_location or location)

def transcribe_audio_file(audio_path: str, chunk_time: int = 600, model_name: str = "gemini-2.5-flash") -> str:
    """
    Splits audio_path into chunk_time (seconds) WAV files and transcribes each using Vertex AI Gemini.
    Saves full transcription to <audio_path_stem>_transcription.txt and returns output file path.
    """
    client = get_vertex_client()
    input_path = Path(audio_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    chunks_dir = input_path.parent / f"{input_path.stem}_chunks"
    chunks_dir.mkdir(exist_ok=True)

    print(f"\n==================================================")
    print(f" Transcribing: {input_path.name}")
    print(f" Chunk Duration: {chunk_time}s")
    print(f" Model: {model_name}")
    print(f"==================================================\n")

    # Step 1: Chunk into 16kHz mono WAVs
    chunk_pattern = chunks_dir / "chunk_%03d.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-f", "segment", "-segment_time", str(chunk_time),
        "-c:a", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(chunk_pattern)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    chunks = sorted(list(chunks_dir.glob("chunk_*.wav")))
    if not chunks:
        raise RuntimeError("ffmpeg failed to create audio chunks.")

    print(f"Created {len(chunks)} chunks.")

    out_txt = input_path.with_name(f"{input_path.stem}_transcription.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"# Transcription of {input_path.name}\n\n")

    prompt = (
        "You are an expert audio transcriber. "
        "Listen to this audio clip carefully and transcribe all spoken words verbatim into their original spoken script "
        "(primarily Khmer script, and English text for any spoken English terms). "
        "Do not translate, summarize, or paraphrase. "
        "Maintain accurate Khmer orthography, subscripting (jeung), and logical line/paragraph breaks. "
        "Output ONLY the exact transcription text."
    )

    full_text = []

    for i, chunk_path in enumerate(chunks, 1):
        print(f"Processing chunk {i}/{len(chunks)} ({chunk_path.name})...")
        with open(chunk_path, "rb") as f:
            audio_bytes = f.read()

        part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")

        max_retries = 3
        transcribed_chunk = ""

        for attempt in range(1, max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[part, prompt]
                )
                if response.text:
                    transcribed_chunk = response.text.strip()
                    break
                else:
                    print(f"  Attempt {attempt} returned empty response.")
            except Exception as e:
                print(f"  Attempt {attempt} failed: {e}")
                time.sleep(3)

        if transcribed_chunk:
            full_text.append(f"\n--- Chunk {i} ---\n\n" + transcribed_chunk)
            with open(out_txt, "a", encoding="utf-8") as f:
                f.write(f"\n\n--- Chunk {i} ---\n\n")
                f.write(transcribed_chunk)
            print(f"  ✅ Chunk {i} completed ({len(transcribed_chunk)} chars)")
        else:
            print(f"  ❌ Chunk {i} failed transcription after {max_retries} retries.")

    # Cleanup temporary local chunks
    shutil.rmtree(chunks_dir, ignore_errors=True)
    print(f"\n🎉 Saved full transcription to: {out_txt}\n")
    return str(out_txt)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    if len(sys.argv) < 2:
        print("Usage: python gemini_tools/transcribe_audio.py <audio_file_1> [audio_file_2 ...]")
        sys.exit(1)

    generated_txts = []
    for target in sys.argv[1:]:
        txt_out = transcribe_audio_file(target)
        generated_txts.append(txt_out)

    print("\n==================================================")
    print(" Running Post-Processing: Formatting Readable DOCX")
    print(" Font Family: Kantumruy Pro")
    print("==================================================\n")

    from gemini_tools.format_and_export_docx import export_chronological_cleaned_docx
    output_docx = str(Path(sys.argv[1]).parent / "Au_Veng_Street_Complete_Transcript.docx")
    export_chronological_cleaned_docx(generated_txts, output_docx)

