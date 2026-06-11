import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()


def prettify_json(data):
    """Returns a nicely formatted JSON string."""
    return json.dumps(data, indent=4, sort_keys=False)


def get_access_token(client_id, client_secret):
    """Fetches a new access token using Client ID and Secret."""
    url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}

    try:
        response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Failed to get token. Status: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return None


def filter_playlist_details(raw_data):
    """Strips away 90% of the useless Spotify data, keeping only what we need."""
    filtered = {
        "id": raw_data.get("id"),
        "name": raw_data.get("name"),
        "description": raw_data.get("description"),
        "url": raw_data.get("external_urls", {}).get("spotify"),
        "image": raw_data.get("images", [{}])[0].get("url") if raw_data.get("images") else None,
        "owner": raw_data.get("owner", {}).get("display_name"),
        "total_tracks": raw_data.get("tracks", {}).get("total"),
        "tracks": []
    }

    # Extract clean track data
    for item in raw_data.get("tracks", {}).get("items", []):
        track = item.get("track")
        if not track:
            continue

        filtered["tracks"].append({
            "id": track.get("id"),
            "name": track.get("name"),
            "artists": [artist.get("name") for artist in track.get("artists", [])],
            "album": track.get("album", {}).get("name"),
            "url": track.get("external_urls", {}).get("spotify"),
            "duration_ms": track.get("duration_ms")
        })

    return filtered


def fetch_single_playlist():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Client ID or Secret not found in .env file.")
        return

    print("Authenticating with Spotify...")
    token = get_access_token(client_id, client_secret)
    if not token: return

    user_input = input("Enter the Spotify Playlist URL or ID: ").strip()
    if not user_input: return

    playlist_id = user_input.split("playlist/")[1].split("?")[0] if "spotify.com" in user_input else user_input

    print(f"\nFetching details for playlist ID: {playlist_id}...")
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            raw_data = response.json()

            # --- PAGINATION LOGIC: Fetch tracks beyond the 100 limit ---
            next_url = raw_data.get("tracks", {}).get("next")
            while next_url:
                print(f"Fetching more tracks... ({len(raw_data['tracks']['items'])} fetched so far)")
                next_response = requests.get(next_url, headers=headers)
                if next_response.status_code == 200:
                    next_data = next_response.json()
                    raw_data["tracks"]["items"].extend(next_data.get("items", []))
                    next_url = next_data.get("next")
                else:
                    print(f"Warning: Failed to fetch next page. Status: {next_response.status_code}")
                    break
            # -----------------------------------------------------------

            # Apply our filter to drastically reduce file size
            clean_data = filter_playlist_details(raw_data)

            with open("clean_playlist_details.json", "w", encoding="utf-8") as f:
                f.write(prettify_json(clean_data))

            print(f"Success! Saved clean data for '{clean_data['name']}' ({len(clean_data['tracks'])} tracks).")
        else:
            print(f"Failed to fetch data. Status Code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    fetch_single_playlist()