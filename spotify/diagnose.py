import os
import json
import requests
from dotenv import load_dotenv
from utils.bifrost_config import get_config

load_dotenv()

def get_access_token(client_id, client_secret):
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
    )
    return resp.json().get("access_token") if resp.status_code == 200 else None

client_id = get_config("SPOTIFY_CLIENT_ID")
client_secret = get_config("SPOTIFY_CLIENT_SECRET")
token = get_access_token(client_id, client_secret)
headers = {"Authorization": f"Bearer {token}"}

USER_ID = "9x6a3knnjv0jabagbsm1ye9hh"
MISSING_ID = "5Os8e1HAREQnRDVDvI1LwJ"

# -----------------------------------------------------------------------
# 1. Dump the RAW full API response for the missing playlist (no filtering)
# -----------------------------------------------------------------------
print("=" * 60)
print("1. RAW FULL RESPONSE — missing playlist")
print("=" * 60)
resp = requests.get(f"https://api.spotify.com/v1/playlists/{MISSING_ID}", headers=headers)
raw = resp.json()
# Remove tracks to keep output readable
raw.pop("tracks", None)
print(json.dumps(raw, indent=2))

# -----------------------------------------------------------------------
# 2. Try fetching user playlists with different offsets manually
#    (in case pagination is buggy and skipping some)
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("2. MANUAL OFFSET SWEEP — all pages raw")
print("=" * 60)
for offset in range(0, 60, 5):
    url = f"https://api.spotify.com/v1/users/{USER_ID}/playlists?limit=5&offset={offset}"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    items = data.get("items", [])
    if not items:
        print(f"  offset={offset}: no more results (total reported: {data.get('total')})")
        break
    for item in items:
        if item:
            print(f"  offset={offset} -> [{item.get('id')}] {item.get('name')} | public={item.get('public')}")

# -----------------------------------------------------------------------
# 3. Check if missing playlist appears under a different user endpoint
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("3. USER PROFILE RAW")
print("=" * 60)
resp = requests.get(f"https://api.spotify.com/v1/users/{USER_ID}", headers=headers)
print(json.dumps(resp.json(), indent=2))

# -----------------------------------------------------------------------
# 4. Compare created_at proxy — snapshot_id prefix encodes a version counter
#    Extract the numeric portion to estimate relative age
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("4. SNAPSHOT ID COMPARISON (visible vs missing)")
print("=" * 60)
url = f"https://api.spotify.com/v1/users/{USER_ID}/playlists?limit=50"
visible = []
while url:
    resp = requests.get(url, headers=headers)
    data = resp.json()
    for item in data.get("items", []):
        if item:
            visible.append(item)
    url = data.get("next")

for v in visible:
    print(f"  [VISIBLE] {v.get('name')[:40]:<40} snapshot={v.get('snapshot_id')}")

resp = requests.get(f"https://api.spotify.com/v1/playlists/{MISSING_ID}", headers=headers)
m = resp.json()
print(f"  [MISSING] {m.get('name')[:40]:<40} snapshot={m.get('snapshot_id')}")