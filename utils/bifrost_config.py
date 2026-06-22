import os
import requests
import json
import time
from dotenv import load_dotenv

# Load local .env first to get the BIFROST_ credentials
load_dotenv()

# Synchronous Pull on Boot with caching (valid for 1 hour)
bifrost_url = os.getenv("BIFROST_URL")
client_id = os.getenv("BIFROST_CLIENT_ID")
webhook_secret = os.getenv("BIFROST_WEBHOOK_SECRET")

cache_file = os.path.join(os.path.dirname(__file__), ".bifrost_cache.json")

def load_cached_keys():
    if os.path.exists(cache_file):
        try:
            mtime = os.path.getmtime(cache_file)
            # Cache is valid for 1 hour
            if time.time() - mtime < 3600:
                with open(cache_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass
    return None

def save_cached_keys(data):
    try:
        with open(cache_file, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

if bifrost_url and client_id and webhook_secret:
    data = load_cached_keys()
    from_cache = True
    
    if data is None:
        endpoint = f"{bifrost_url.rstrip('/')}/api/v1/config"
        headers = {
            "X-Client-ID": client_id,
            "X-Webhook-Secret": webhook_secret
        }
        try:
            response = requests.get(endpoint, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            save_cached_keys(data)
            from_cache = False
        except Exception as e:
            print(f"❌ Bifrost: Failed to fetch secure config - {e}")
            
    if data:
        # Dump decrypted keys straight into local memory
        keys_loaded = 0
        for key, value in data.get("data", {}).get("api_keys", {}).items():
            if value:
                os.environ[key] = str(value)
                keys_loaded += 1
                
        source = "cache" if from_cache else "pull"
        print(f"✅ Bifrost: Loaded {keys_loaded} keys into memory ({source}).")
else:
    print("⚠️ Warning: Missing Bifrost credentials. Running with standard local env.")

def get_config(key_name: str, default: str = "") -> str:
    """
    Fetches a config value from the environment.
    (Keys were synchronously injected into os.environ at boot via Bifrost)
    """
    safe_key_name = key_name.strip()
    fallback = os.getenv(safe_key_name)
    if fallback is not None:
        return fallback

    return default
