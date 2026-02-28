import requests


def get_access_token(client_id, client_secret):
    """Fetches a new access token using Client ID and Secret."""
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }

    try:
        response = requests.post(url, headers=headers, data=data, auth=(client_id, client_secret))
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Failed to get access token. Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching access token: {e}")
        return None