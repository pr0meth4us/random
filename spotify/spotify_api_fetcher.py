import os
import json
import requests
from dotenv import load_dotenv
from utils.bifrost_config import get_config

load_dotenv()


def prettify_json(data):
    return json.dumps(data, indent=4, sort_keys=False)


def get_access_token(client_id, client_secret):
    """Uses Client Credentials flow — no user login, fully silent, public data only."""
    url = "https://accounts.spotify.com/api/token"
    response = requests.post(
        url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials"},
        auth=("2810146adb0d489a8cf54072afa9324d", "2d3593ebf3f04ffd8cf31f6756c2f67f"),
    )
    return response.json().get("access_token") if response.status_code == 200 else None


def get_all_pages(url, headers):
    """Generic paginator — follows 'next' until exhausted."""
    results = []
    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"  -> Warning: {resp.status_code} on {url}")
            break
        data = resp.json()
        results.extend(data.get("items", []))
        url = data.get("next")
    return results


def build_track(item):
    """Extracts a rich set of fields from a playlist track item."""
    track = item.get("track")
    if not track or track.get("type") != "track":
        # Skip episodes / local files / nulls
        return None

    album = track.get("album", {})
    artists = track.get("artists", [])

    return {
        "name": track.get("name"),
        "id": track.get("id"),
        "uri": track.get("uri"),
        "url": track.get("external_urls", {}).get("spotify"),
        "duration_ms": track.get("duration_ms"),
        "duration_readable": ms_to_readable(track.get("duration_ms", 0)),
        "explicit": track.get("explicit"),
        "popularity": track.get("popularity"),       # 0–100
        "track_number": track.get("track_number"),
        "disc_number": track.get("disc_number"),
        "isrc": track.get("external_ids", {}).get("isrc"),
        "preview_url": track.get("preview_url"),     # 30-sec clip URL (if available)
        "artists": [
            {"name": a.get("name"), "id": a.get("id"), "url": a.get("external_urls", {}).get("spotify")}
            for a in artists
        ],
        "album": {
            "name": album.get("name"),
            "id": album.get("id"),
            "url": album.get("external_urls", {}).get("spotify"),
            "type": album.get("album_type"),         # album / single / compilation
            "release_date": album.get("release_date"),
            "total_tracks": album.get("total_tracks"),
            "image": album.get("images", [{}])[0].get("url") if album.get("images") else None,
        },
        "added_at": item.get("added_at"),            # When it was added to this playlist
        "added_by": item.get("added_by", {}).get("id"),
    }


def ms_to_readable(ms):
    """Converts milliseconds to m:ss string."""
    seconds = ms // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def get_all_tracks(playlist_id, headers):
    """Fetches every track in a playlist with rich metadata."""
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"
    raw_items = get_all_pages(url, headers)
    tracks = []
    for item in raw_items:
        track = build_track(item)
        if track:
            tracks.append(track)
    return tracks


def get_all_user_playlists(user_id, headers):
    """
    Fetches every PUBLIC playlist owned by the user.
    The client credentials flow never triggers any notification on Spotify's end —
    it's the same as an anonymous read of a public profile.
    Returns (playlists, spotify_reported_total) so we can verify nothing was missed.
    """
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists?limit=50"
    results = []
    spotify_total = 0

    while url:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"  -> Warning: {resp.status_code} on {url}")
            break
        data = resp.json()
        if spotify_total == 0:
            spotify_total = data.get("total", 0)  # Capture on first page only
        results.extend(data.get("items", []))
        url = data.get("next")

    return results, spotify_total


def build_playlist(item, headers, index, total):
    """Enriches a raw playlist object with full track data and extra fields."""
    playlist_id = item.get("id")
    name = item.get("name", "Untitled")
    print(f"  [{index}/{total}] {name} ({item.get('tracks', {}).get('total', '?')} tracks)")

    tracks = get_all_tracks(playlist_id, headers)
    owner = item.get("owner", {})

    return {
        "id": playlist_id,
        "name": name,
        "description": item.get("description"),
        "url": item.get("external_urls", {}).get("spotify"),
        "uri": item.get("uri"),
        "public": item.get("public"),
        "collaborative": item.get("collaborative"),
        "snapshot_id": item.get("snapshot_id"),     # Unique version fingerprint
        "image": item.get("images", [{}])[0].get("url") if item.get("images") else None,
        "owner": {
            "display_name": owner.get("display_name"),
            "id": owner.get("id"),
            "url": owner.get("external_urls", {}).get("spotify"),
        },
        "total_tracks_reported": item.get("tracks", {}).get("total"),
        "total_tracks_fetched": len(tracks),
        "tracks": tracks,
    }


def fetch_user_playlists():
    client_id = get_config("SPOTIFY_CLIENT_ID")
    client_secret = get_config("SPOTIFY_CLIENT_SECRET")

    # if not client_id or not client_secret:
    #     print("Error: SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET missing from .env")
    #     return

    token = get_access_token(client_id, client_secret)
    if not token:
        print("Error: Could not obtain access token.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    user_id = input("Enter the Spotify User ID: ").strip()
    if not user_id:
        return

    print(f"\nFetching public playlists for user: {user_id} ...")
    raw_playlists, spotify_total = get_all_user_playlists(user_id, headers)

    if not raw_playlists:
        print("No public playlists found (or user doesn't exist).")
        return

    fetched_count = len(raw_playlists)
    print(f"Spotify reports {spotify_total} total — fetched {fetched_count} public playlists.")
    if fetched_count < spotify_total:
        print(f"  -> {spotify_total - fetched_count} skipped (private, invisible via the API).")
    else:
        print(f"  -> All public playlists accounted for.")
    print("Fetching track data...\n")

    playlists = []
    for i, item in enumerate(raw_playlists, 1):
        if item:
            playlists.append(build_playlist(item, headers, i, len(raw_playlists)))

    output = {
        "user_id": user_id,
        "total_playlists": len(playlists),
        "playlists": playlists,
    }

    filename = f"{user_id}_playlists.json"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(prettify_json(output))

    total_tracks = sum(p["total_tracks_fetched"] for p in playlists)
    print(f"\nDone! Saved {len(playlists)} playlists / {total_tracks} tracks → {filename}")


if __name__ == "__main__":
    fetch_user_playlists()