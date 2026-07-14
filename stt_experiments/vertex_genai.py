import os
import sys

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/sa.json"

from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project="egd-ai-services-1782364268", location="us-central1")

audio_path = "test_vocals_16k_full.wav"
print(f"Reading audio from {audio_path}...")
with open(audio_path, "rb") as f:
    audio_bytes = f.read()

print(f"Read {len(audio_bytes)} bytes. Preparing Vertex AI request...")

prompt = (
    "You are an expert transcriber of the Khmer language. "
    "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
    "Do not translate it to English. "
    "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
    "Only output the transcribed text."
)

print("Sending to Gemini 1.5 Pro via Vertex AI (google.genai)...")
try:
    response = client.models.generate_content(
        model="gemini-1.5-flash-001",
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type='audio/wav',
            ),
            prompt
        ]
    )
    
    print("\n--- TRANSCRIPTION ---\n")
    print(response.text)
    print("\n---------------------\n")
    
    with open(f"{audio_path}.gemini.txt", "w") as f:
        f.write(response.text)
    print(f"Saved to {audio_path}.gemini.txt")
except Exception as e:
    print(f"FAILED: {e}")
