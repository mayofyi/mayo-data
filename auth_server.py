"""
Instagram OAuth server.

Handles the two-step OAuth flow for Instagram Graph API access:
  /login    — redirects the user to Instagram's authorization page
  /callback — exchanges the auth code for a long-lived token and saves it to .env

Usage:
    1. Start ngrok: ngrok http 5000
    2. Set REDIRECT_URI=https://<ngrok-url>/callback in .env
    3. Add that URL to Meta app's Valid OAuth Redirect URIs
    4. Run: python auth_server.py
    5. Send users to: https://<ngrok-url>/login
"""

import os

import requests
from dotenv import load_dotenv
from flask import Flask, redirect, request

load_dotenv()

META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

app = Flask(__name__)


@app.route("/login")
def login():
    auth_url = (
        "https://www.instagram.com/oauth/authorize"
        f"?client_id={META_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=instagram_business_basic"
        "&response_type=code"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    code = request.args.get("code", "")
    # Meta appends #_ to the code; strip it
    code = code.split("#")[0]

    # Exchange code for short-lived token
    token_response = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        timeout=15,
    )
    token_response.raise_for_status()
    short_lived_token = token_response.json()["access_token"]

    # Upgrade to long-lived token (valid 60 days)
    long_lived_response = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": META_APP_SECRET,
            "access_token": short_lived_token,
        },
        timeout=15,
    )
    long_lived_response.raise_for_status()
    long_lived_token = long_lived_response.json()["access_token"]

    return f"""
    <html>
    <body style="font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 20px;">
        <h2>You're all set!</h2>
        <p>Please copy the token below and send it to your Mayo contact:</p>
        <textarea rows="4" style="width:100%; font-size:12px; padding:8px;">{long_lived_token}</textarea>
        <p style="color: gray; font-size: 13px;">You can close this tab after sending the token.</p>
    </body>
    </html>
    """


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
