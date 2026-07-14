import os
import sys
import time
from google import genai
from google.genai import types

api_key = "YOUR_API_KEY"
client = genai.Client(api_key=api_key)

audio_path = "test_vocals_16k_full.wav"
print(f"Uploading {audio_path} to Gemini...")
audio_file = client.files.upload(file=audio_path)
print(f"File uploaded. File URI: {audio_file.uri}")

print("Waiting for audio processing...")
while True:
    file_info = client.files.get(name=audio_file.name)
    if file_info.state.name == "ACTIVE":
        print("Audio is ready!")
        break
    elif file_info.state.name == "FAILED":
        print("Audio processing failed.")
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
print(f"Sending request to {model_name}...")

max_retries = 3
for attempt in range(max_retries):
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[audio_file, prompt]
        )
        print("\n--- TRANSCRIPTION ---\n")
        print(response.text)
        print("\n---------------------\n")
        
        with open("gemini_final_transcript.txt", "w") as f:
            f.write(response.text or "NO TEXT")
        break
    except Exception as e:
        print(f"Attempt {attempt+1} FAILED: {e}")
        if attempt < max_retries - 1:
            time.sleep(5)

client.files.delete(name=audio_file.name)
