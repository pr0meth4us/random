import os
import sys

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/sa.json"

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Part

aiplatform.init(project="egd-ai-services-1782364268", location="us-central1")

try:
    model = GenerativeModel("gemini-1.5-pro")
    
    prompt = "Translate this word to Khmer: Hello"
    response = model.generate_content(prompt)
    print("SUCCESS! Vertex AI works:", response.text)
except Exception as e:
    print("FAILED:", str(e))
