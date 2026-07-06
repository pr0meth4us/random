import os
import sys
import requests
import json
import time
from dotenv import load_dotenv

# Load local .env first
load_dotenv()

# Try importing from the central local SDK first (for shared cache and local de-duplication)
sdk_path = "/Users/nicksng/code/bifrost/sdk/python"
try:
    if os.path.exists(sdk_path):
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)
        from bifrost_client import get_config
    else:
        raise ImportError
except ImportError:
    # Fallback to self-contained execution in production / container environments
    bifrost_url = os.getenv("BIFROST_URL")
    client_id = os.getenv("BIFROST_CLIENT_ID")
    webhook_secret = os.getenv("BIFROST_WEBHOOK_SECRET")

    # In production container, cache locally in /tmp or script directory
    cache_file = "/tmp/.bifrost_cache.json" if os.name != 'nt' else os.path.join(os.path.dirname(__file__), ".bifrost_cache.json")

    def load_cached_keys():
        if os.path.exists(cache_file):
            try:
                mtime = os.path.getmtime(cache_file)
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
        if data is None:
            endpoint = f"{bifrost_url.rstrip('/')}/api/v1/config"
            headers = {
                "X-Client-ID": client_id,
                "X-Webhook-Secret": webhook_secret
            }
            try:
                response = requests.get(endpoint, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                save_cached_keys(data)
            except Exception as e:
                # Silence logging on headless environments if fallback exists
                pass
                
        if data:
            keys_loaded = 0
            for key, value in data.get("data", {}).get("api_keys", {}).items():
                if value:
                    os.environ[key] = str(value)
                    keys_loaded += 1

    def get_config(key_name: str, default: str = "") -> str:
        safe_key_name = key_name.strip()
        val = os.getenv(safe_key_name)
        if val is not None:
            return val
        return default
