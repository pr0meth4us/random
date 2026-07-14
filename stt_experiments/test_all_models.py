import os
import time
from google import genai

client = genai.Client(api_key="YOUR_API_KEY")

prompt = "Hello, reply with exactly one word: 'yes'."

available_models = []

for m in client.models.list():
    model_name = m.name
    # Skip embedding, image, audio, tts models
    if "embedding" in model_name or "image" in model_name or "tts" in model_name or "audio" in model_name or "veo" in model_name or "imagen" in model_name:
        continue
        
    # We only care about generative text models
    short_name = model_name.replace("models/", "")
    
    print(f"Testing {short_name}...")
    try:
        response = client.models.generate_content(
            model=short_name,
            contents=prompt
        )
        print(f"✅ SUCCESS: {short_name}")
        available_models.append(short_name)
    except Exception as e:
        err_msg = str(e)
        if "RESOURCE_EXHAUSTED" in err_msg:
            print(f"❌ FAILED (Quota Exceeded / Free Tier limit 0): {short_name}")
        elif "NOT_FOUND" in err_msg:
            print(f"❌ FAILED (Not Found): {short_name}")
        else:
            print(f"❌ FAILED ({err_msg}): {short_name}")
            
    time.sleep(1) # Prevent spamming

print("\n--- WORKING MODELS ---")
for am in available_models:
    print(am)
