import os
import sys
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.append(str(PROJECT_DIR))

from google import genai
from utils.bifrost_config import get_config

load_dotenv()
GEMINI_API_KEY = get_config('GEMINI_API_KEY', '').replace('\ufeff', '').strip()

def get_client():
    # Try Vertex AI first if service account is available
    sa_path = "/Users/nicksng/code/egd platform/.secrets/claude.json"
    if os.path.exists(sa_path):
        print(f"Using Vertex AI with service account: {sa_path}")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
        try:
            return genai.Client(
                vertexai=True,
                project="egd-ai-services-1782364268",
                location="us-central1" # Update this to 'us' or 'us-central1' if the model is enabled
            )
        except Exception as e:
            print(f"Vertex AI initialization failed: {e}")
            
    # Fallback to AI Studio Key
    GEMINI_API_KEY = get_config('GEMINI_API_KEY', '').replace('\ufeff', '').strip()
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is missing from Bifrost/.env")
        sys.exit(1)
        
    print("Using AI Studio API Key from Bifrost...")
    return genai.Client(api_key=GEMINI_API_KEY)

client = get_client()

def transcribe_audio(audio_path):
    print(f"Uploading audio from {audio_path}...")
    try:
        uploaded_file = client.files.upload(file=audio_path)
    except Exception as e:
        if "leaked" in str(e).lower() or "permission_denied" in str(e).lower():
            print("\n❌ ERROR: Your AI Studio API Key has been revoked/leaked. Please generate a new key and update it in Bifrost.")
        else:
            print(f"\n❌ ERROR uploading file: {e}")
        return
    
    print("Sending to Gemini 1.5 Pro...")
    prompt = (
        "You are an expert transcriber of the Khmer language. "
        "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
        "Do not translate it to English. "
        "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
        "Only output the transcribed text."
    )

    try:
        response = client.models.generate_content(
            model="gemini-1.5-pro", # If using Vertex AI, ensure this model is enabled in your project
            contents=[uploaded_file, prompt]
        )
        print("\n--- TRANSCRIPTION ---\n")
        print(response.text)
        print("\n---------------------\n")
    except Exception as e:
        if "not_found" in str(e).lower() or "404" in str(e).lower():
            print("\n❌ ERROR: Model not found in Vertex AI. You may need to enable 'gemini-1.5-pro' in Vertex AI Model Garden for your project, or use a valid multi-region (e.g. 'us').")
        else:
            print(f"\n❌ ERROR generating content: {e}")

if __name__ == "__main__":
    audio_file = "test_audio_short.wav"
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} not found.")
    else:
        transcribe_audio(audio_file)
