import os
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Add the parent directory to sys.path so we can import from 'utils'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.bifrost_config import get_config

def get_stats():
    client_id = get_config("SPOTIFY_CLIENT_ID") or "2810146adb0d489a8cf54072afa9324d"
    client_secret = get_config("SPOTIFY_CLIENT_SECRET") or "2d3593ebf3f04ffd8cf31f6756c2f67f"
    redirect_uri = get_config("SPOTIFY_REDIRECT_URI") or "http://localhost:8080"
    
    if not client_id or not client_secret:
        print("Please ensure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are in your .env file.")
        return
        
    scope = "user-top-read user-read-recently-played"
    
    print(f"Make sure you have added '{redirect_uri}' as a Redirect URI in your Spotify Developer Dashboard!")
    print("If it is your first time running this, a browser window will open for you to log in.")
    print("---------------------------------------------------------------------------------------")
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        open_browser=True
    ))
    
    # Get top artists
    print("\n=== Your Top Artists (Last 6 Months) ===")
    results = sp.current_user_top_artists(limit=10, time_range='medium_term')
    for idx, item in enumerate(results['items']):
        print(f"{idx + 1}. {item['name']}")

    # Get top tracks
    print("\n=== Your Top Tracks (Last 6 Months) ===")
    results = sp.current_user_top_tracks(limit=10, time_range='medium_term')
    for idx, item in enumerate(results['items']):
        artists = ", ".join([artist['name'] for artist in item['artists']])
        print(f"{idx + 1}. {item['name']} - {artists}")
        
    # Get recently played
    print("\n=== Recently Played Tracks ===")
    results = sp.current_user_recently_played(limit=5)
    for idx, item in enumerate(results['items']):
        track = item['track']
        artists = ", ".join([artist['name'] for artist in track['artists']])
        print(f"{idx + 1}. {track['name']} - {artists}")

if __name__ == "__main__":
    get_stats()
