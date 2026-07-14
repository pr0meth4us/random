import os
import sys

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/sa.json"

from google.cloud import speech

def transcribe_gcs(gcs_uri):
    """Asynchronously transcribes the audio file specified by the gcs_uri."""
    print(f"Transcribing {gcs_uri}...")
    client = speech.SpeechClient()

    audio = speech.RecognitionAudio(uri=gcs_uri)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="km-KH",
    )

    operation = client.long_running_recognize(config=config, audio=audio)

    print("Waiting for operation to complete...")
    response = operation.result(timeout=300)

    full_transcript = []
    for result in response.results:
        print(f"Transcript: {result.alternatives[0].transcript}")
        print(f"Confidence: {result.alternatives[0].confidence}")
        full_transcript.append(result.alternatives[0].transcript)
        
    print("\n\n--- FULL TRANSCRIPT ---")
    print(" ".join(full_transcript))
    print("-----------------------\n")
    
    with open("full_transcript.txt", "w") as f:
        f.write("\n".join(full_transcript))

if __name__ == "__main__":
    transcribe_gcs("gs://egd-ai-services-audio-bucket-1234/test_vocals_16k_full.wav")
