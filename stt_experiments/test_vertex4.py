import os
import sys
from vertexai.generative_models import GenerativeModel
import vertexai

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/nicksng/code/egd platform/.secrets/claude.json"

try:
    vertexai.init(project="egd-ai-services-1782364268", location="us-central1")
    model = GenerativeModel("gemini-1.5-pro")
    print("Client initialized!")
    
    response = model.generate_content("Say hello!")
    print(response.text)
except Exception as e:
    print("Error:", e)
    sys.exit(1)
