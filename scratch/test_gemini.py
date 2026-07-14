import os
from google import genai

def test_api():
    # Set the environment variable
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    client = genai.Client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Tell me "API is working!"'
    )
    print(response.text)

if __name__ == "__main__":
    test_api()
