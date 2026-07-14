import os
import sys
from google import genai

GEMINI_API_KEY = "YOUR_API_KEY"
client = genai.Client(api_key=GEMINI_API_KEY)

def transcribe_audio(audio_path):
    print(f"Uploading audio from {audio_path}...")
    uploaded_file = client.files.upload(file=audio_path)
    
    print("Sending to Gemini 1.5 Pro...")
    prompt = (
        "You are an expert transcriber of the Khmer language. "
        "Listen to this audio clip and transcribe the spoken words exactly into Khmer script. "
        "Do not translate it to English. "
        "Ensure correct orthography (spelling), use correct subscripting (jeung), and apply logical spacing. "
        "Only output the transcribed text."
    )

    response = client.models.generate_content(
        model="gemini-1.5-pro",
        contents=[uploaded_file, prompt]
    )
    
    print("\n--- TRANSCRIPTION ---\n")
    print(response.text)
    print("\n---------------------\n")
    
    with open(f"{audio_path}.gemini.txt", "w") as f:
        f.write(response.text)

if __name__ == "__main__":
    audio_file = sys.argv[1] if len(sys.argv) > 1 else "separated/htdemucs/test_audio_2/vocals.wav"
    transcribe_audio(audio_file)
