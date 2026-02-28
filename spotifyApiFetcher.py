import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()


def fetch_spotify_playlists():
    # 1. Securely get the token from the .env file
    token = os.getenv("SPOTIFY_TOKEN")

    if not token:
        print("Error: SPOTIFY_TOKEN not found. Please create a .env file and add your token.")
        return

    # 2. Ask the user for the Spotify User ID
    user_id = input("Enter the Spotify User ID: ").strip()

    if not user_id:
        print("Error: User ID cannot be empty.")
        return

    print(f"\nFetching playlists for user: {user_id}...")

    # Spotify API Endpoint (fetching up to 50 playlists)
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists?limit=50&offset=0"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        # 3. Make the request to Spotify
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()

            # 4. Save the data to data.json for the HTML file to read
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

            print(f"Success! Saved {len(data.get('items', []))} playlists to data.json")
        else:
            print(f"Failed to fetch data. Status Code: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    fetch_spotify_playlists()