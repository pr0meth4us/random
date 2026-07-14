import os
from google.cloud import speech

# Initialize Google Cloud Speech Client
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/claude.json"
client = speech.SpeechClient()

def transcribe_audio(audio_path):
    print(f"Loading audio from {audio_path}...")
    with open(audio_path, "rb") as f:
        content = f.read()

    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="km-KH",
        enable_automatic_punctuation=True,
    )

    print("Sending to Google Cloud Speech (v1)...")
    # Using synchronous recognize since the clip is short. If it fails due to length, we might need long_running_recognize
    try:
        response = client.recognize(config=config, audio=audio)
        print("\n--- TRANSCRIPTION ---\n")
        for result in response.results:
            print("Transcript: {}".format(result.alternatives[0].transcript))
            print("Confidence: {}".format(result.alternatives[0].confidence))
        print("\n---------------------\n")
    except Exception as e:
        print(f"Error during recognition: {e}")

if __name__ == "__main__":
    import sys; audio_file = sys.argv[1] if len(sys.argv) > 1 else "test_audio_short.wav"
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} not found.")
    else:
        transcribe_audio(audio_file)
