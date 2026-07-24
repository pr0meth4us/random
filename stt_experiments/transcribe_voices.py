import os
import whisper
import json

VOICE_DIR = "/Users/nicksng/code/random/voice_messages"
OUTPUT_FILE = "/Users/nicksng/code/random/transcriptions.json"

def main():
    print("Loading Whisper 'small' model (this will download ~460MB if it's the first time)...")
    # 'small' is used instead of 'base' for better accuracy, especially if there's non-English speech like Khmer
    model = whisper.load_model("small")
    print("Model loaded successfully!\n")
    
    transcriptions = {}
    
    if not os.path.exists(VOICE_DIR):
        print(f"Directory {VOICE_DIR} not found.")
        return
        
    files = [f for f in os.listdir(VOICE_DIR) if f.endswith(".ogg")]
    print(f"Found {len(files)} voice messages to transcribe.\n")
    
    for idx, filename in enumerate(files, 1):
        file_path = os.path.join(VOICE_DIR, filename)
        print(f"Transcribing {idx}/{len(files)}: {filename}...")
        
        try:
            # Whisper handles audio loading via ffmpeg automatically
            result = model.transcribe(file_path)
            text = result["text"].strip()
            lang = result.get("language", "unknown")
            
            transcriptions[filename] = {
                "text": text,
                "language": lang
            }
            print(f"  -> [{lang}] {text}\n")
        except Exception as e:
            print(f"  -> Error transcribing {filename}: {e}\n")
            
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(transcriptions, f, ensure_ascii=False, indent=2)
        
    print(f"Done! Saved all transcriptions to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
