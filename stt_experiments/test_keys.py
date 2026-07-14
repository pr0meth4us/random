import os
import sys
from pathlib import Path
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.append(str(SCRIPT_DIR.parent))

from utils.bifrost_config import get_config
load_dotenv()

print("OpenAI:", get_config('OPENAI_API_KEY'))
print("Groq:", get_config('GROQ_API_KEY'))
print("Anthropic:", get_config('ANTHROPIC_API_KEY'))
