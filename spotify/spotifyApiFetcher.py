import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def prettify_json(data):
    return json.dumps(data, indent=4, sort_keys=False)


def get_access_token(client_id, client_secret):
    url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials"}

    response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
    return response.json().get("access_token") if response.status_code == 200 else None


def get_minimal_tracks(playlist_id, token):
    """Fetches the tracks for a specific playlist and extracts only the name and artists."""
    # Fetch up to 100 tracks at a time and paginate to get all of them
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"
    headers = {"Authorization": f"Bearer {token}"}
    tracks = []

    while url:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('items', []):
                    track = item.get('track')
                    if not track:
                        continue

                    tracks.append({
                        "name": track.get("name"),
                        "artists": [artist.get("name") for artist in track.get("artists", [])]
                    })
                # Check if there's a next page of tracks and update the url to fetch it
                url = data.get('next')
            else:
                print(f"  -> Warning: Status {response.status_code}")
                break
        except Exception as e:
            print(f"  -> Error fetching tracks for {playlist_id}: {e}")
            break

    return tracks


def filter_user_playlists(raw_data, token):
    """Strips out all the unnecessary Spotify API bloat and attaches minimal track data."""
    filtered_items = []
    items = raw_data.get('items', [])

    for index, item in enumerate(items, 1):
        if not item:
            continue

        playlist_id = item.get("id")
        playlist_name = item.get("name")

        # Log progress to the console so you know it isn't frozen
        print(f"[{index}/{len(items)}] Fetching tracks for: {playlist_name}")

        # Go grab the tracks for this specific playlist
        minimal_tracks = get_minimal_tracks(playlist_id, token)

        filtered_items.append({
            "id": playlist_id,
            "name": playlist_name,
            "description": item.get("description"),
            "url": item.get("external_urls", {}).get("spotify"),
            "image": item.get("images", [{}])[0].get("url") if item.get("images") else None,
            "owner": item.get("owner", {}).get("display_name"),
            "total_tracks": item.get("tracks", {}).get("total"),
            "tracks": minimal_tracks  # Inject the fetched tracks here
        })

    return {
        "total_returned": len(filtered_items),
        "total_in_spotify": raw_data.get("total"),
        "playlists": filtered_items
    }


def fetch_user_playlists():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Missing credentials in .env")
        return

    token = get_access_token(client_id, client_secret)
    if not token: return

    user_id = input("Enter the Spotify User ID: ").strip()
    if not user_id: return

    print(f"\nFetching profile directory for user: {user_id}...")
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists?limit=50&offset=0"
    headers = {"Authorization": f"Bearer {token}"}

    all_playlist_items = []
    total_spotify_playlists = 0

    try:
        # Loop to get all playlists if the user has more than 50
        while url:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                all_playlist_items.extend(data.get('items', []))
                total_spotify_playlists = data.get('total', 0)
                url = data.get('next')  # Update url to fetch the next page of playlists
            else:
                print(f"Failed. Status: {response.status_code}")
                break

        if all_playlist_items:
            print(f"Found {len(all_playlist_items)} playlists. Gathering minimal track data...")

            # Reconstruct the raw_data object expected by our filter function
            raw_data = {"items": all_playlist_items, "total": total_spotify_playlists}

            # Apply our filter, which now also fetches all tracks without limits
            clean_data = filter_user_playlists(raw_data, token)

            with open("clean_user_playlists.json", "w", encoding="utf-8") as f:
                f.write(prettify_json(clean_data))

            print(
                f"\nSuccess! Saved {len(clean_data['playlists'])} clean playlists (with track data) to clean_user_playlists.json.")
        else:
            print("No playlists found or failed to fetch.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    fetch_user_playlists()