import os
import sys

# Authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/sa.json"

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Part

aiplatform.init(project="egd-ai-services-1782364268", location="us-central1")

def transcribe(audio_path):
    print(f"Reading audio from {audio_path}...")
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    
    print(f"Read {len(audio_bytes)} bytes. Preparing Vertex AI request...")
    audio_part = Part.from_data(data=audio_bytes, mime_type="audio/wav")
    
    model = GenerativeModel("gemini-1.5-pro-002")
    
    prompt = (
        "You are an expert transcriber of the Khmer language. "
        "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
        "Do not translate it to English. "
        "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
        "Only output the transcribed text."
    )
    
    print("Sending to Gemini 1.5 Pro via Vertex AI...")
    response = model.generate_content([audio_part, prompt])
    
    print("\n--- TRANSCRIPTION ---\n")
    print(response.text)
    print("\n---------------------\n")
    
    with open(f"{audio_path}.gemini.txt", "w") as f:
        f.write(response.text)
    print(f"Saved to {audio_path}.gemini.txt")

if __name__ == "__main__":
    transcribe("test_vocals_16k_full.wav")
