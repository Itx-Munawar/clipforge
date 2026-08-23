"""OAuth authentication helper for YouTube Data API v3.

Setup instructions:
1. Go to https://console.cloud.google.com/
2. Create a project (or select existing)
3. Enable "YouTube Data API v3"
4. Go to APIs & Services > Credentials
5. Create OAuth 2.0 Client ID (Desktop app)
6. Download the JSON file and save as 'client_secret.json' in this folder

First run will open a browser for Google sign-in.
After that, tokens are cached in 'token.json'.
"""

import os
import json

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes needed for YouTube upload + reading channel info
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = "token.json"


def get_youtube_service():
    """Authenticate and return a YouTube API service object."""
    creds = None

    # Load cached token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid token, do OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                print("")
                print("=" * 60)
                print("  YouTube API Setup Required")
                print("=" * 60)
                print("")
                print("  1. Go to: https://console.cloud.google.com/")
                print("  2. Create/select a project")
                print("  3. Enable 'YouTube Data API v3'")
                print("  4. Go to: APIs & Services > Credentials")
                print("  5. Create OAuth 2.0 Client ID (Desktop app)")
                print(f"  6. Download JSON, save as '{CLIENT_SECRET_FILE}'")
                print(f"       in: {os.path.abspath('.')}")
                print("")
                print("  Then run this script again.")
                print("=" * 60)
                raise FileNotFoundError(
                    f"'{CLIENT_SECRET_FILE}' not found. Follow setup instructions above."
                )

            print("")
            print("Opening browser for Google sign-in...")
            print("(A popup will appear — sign in with your YouTube account)")
            print("")

            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            # port=0 picks a random available port
            creds = flow.run_local_server(port=0, prompt="consent")

        # Save token for next time
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print("Token saved to token.json")
        print("")

    return creds


def test_auth():
    """Quick test to verify authentication works."""
    from googleapiclient.discovery import build

    creds = get_youtube_service()
    youtube = build("youtube", "v3", credentials=creds)

    # Get authenticated user's channel info
    result = youtube.channels().list(part="snippet", mine=True).execute()

    if result.get("items"):
        channel = result["items"][0]["snippet"]
        print(f"Authenticated as: {channel['title']}")
        return True
    else:
        print("No channel found for this account.")
        return False


if __name__ == "__main__":
    test_auth()
