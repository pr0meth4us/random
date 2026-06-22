import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.append(str(PROJECT_DIR))

from google import genai
from utils.bifrost_config import get_config

# Load environment variables
load_dotenv()

GEMINI_API_KEY = get_config('GEMINI_API_KEY', '').replace('\ufeff', '').strip()
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY is missing from your .env file.")
    sys.exit(1)

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

def copy_to_clipboard(text):
    """Copies text to the macOS clipboard using pbcopy."""
    process = subprocess.Popen('pbcopy', env={'LANG': 'en_US.UTF-8'}, stdin=subprocess.PIPE)
    process.communicate(text.encode('utf-8'))

def main():
    print("=== Quick Gemini Answerer ===")
    print("(Type your question and press Enter. The answer will automatically copy to your clipboard.)")
    print("(Press Ctrl+C to exit)\n")
    
    while True:
        try:
            # Get user input
            prompt = input("Ask Gemini: ")
            if not prompt.strip():
                continue
            
            print("Thinking...")
            
            # Query Gemini
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            answer = response.text.strip()
            
            # Print and copy answer
            print(f"\nGemini:\n{answer}")
            copy_to_clipboard(answer)
            print("\n[✓ Copied to clipboard!]\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n[!] Error: {e}\n")

if __name__ == "__main__":
    main()
