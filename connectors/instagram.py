"""
Instagram Graph API connector.

Fetches profile info, recent media, and monthly insights for an Instagram
Business/Creator account. Caches raw responses to data/communities/{account}/instagram.json.

Usage (direct):
    python connectors/instagram.py
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://graph.instagram.com/v21.0"
ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the Instagram Graph API."""
    params = params or {}
    params["access_token"] = ACCESS_TOKEN
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def _cache(account_name: str, data: dict) -> None:
    """Write raw API data to data/communities/{account_name}/instagram.json."""
    cache_dir = Path("data/communities") / account_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "instagram.json"
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)


# ── Public API ────────────────────────────────────────────────────────────────

def get_profile() -> dict:
    """
    Fetch account profile data.

    Returns:
        {
            "id": str,
            "name": str,
            "biography": str,
            "followers_count": int,
            "website": str,
        }
    """
    data = _get("/me", {"fields": "id,username,name,biography,followers_count,website"})
    return {
        "id": data.get("id"),
        "username": data.get("username", ""),
        "name": data.get("name"),
        "biography": data.get("biography", ""),
        "followers_count": data.get("followers_count", 0),
        "website": data.get("website", ""),
    }


def get_media(user_id: str) -> list[dict]:
    """
    Fetch the last 20 posts for a user.

    Args:
        user_id: The Instagram user ID (from get_profile).

    Returns:
        List of dicts with keys: id, caption, like_count, comments_count,
        timestamp, media_type.
    """
    data = _get(
        f"/{user_id}/media",
        {
            "fields": "id,caption,like_count,comments_count,saved_count,timestamp,media_type,media_url,thumbnail_url,permalink",
            "limit": 20,
        },
    )
    return data.get("data", [])


def get_insights(user_id: str) -> dict:
    """
    Fetch monthly engagement insights.

    Uses valid v21.0 metrics: reach, profile_views, accounts_engaged,
    total_interactions, views. Returns zeros for any metric unavailable
    (e.g. new accounts with insufficient data).

    Args:
        user_id: The Instagram user ID (from get_profile).

    Returns:
        {
            "reach": int,
            "profile_views": int,
            "accounts_engaged": int,
            "total_interactions": int,
            "views": int,
        }
    """
    metrics = "reach,profile_views,accounts_engaged,total_interactions,views"
    try:
        data = _get(
            f"/{user_id}/insights",
            {"metric": metrics, "period": "month"},
        )
    except requests.exceptions.HTTPError as e:
        print(f"  [insights] API error ({e.response.status_code}): "
              f"{e.response.json().get('error', {}).get('message', str(e))}")
        data = {}

    result = {}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        # Sum daily values if present, otherwise take last period value
        if values:
            total = sum(v.get("value", 0) for v in values if isinstance(v.get("value"), (int, float)))
            result[name] = total if total else values[-1].get("value", 0)
        else:
            result[name] = 0

    return {
        "reach": result.get("reach", 0),
        "profile_views": result.get("profile_views", 0),
        "accounts_engaged": result.get("accounts_engaged", 0),
        "total_interactions": result.get("total_interactions", 0),
        "views": result.get("views", 0),
    }


def get_media_shares(media: list[dict]) -> dict:
    """
    Fetch share counts for each post via the media insights endpoint.
    Requires instagram_business_manage_insights permission.

    Args:
        media: List of post dicts from get_media.

    Returns:
        Dict mapping media_id -> share_count.
    """
    shares = {}
    for post in media:
        media_id = post.get("id")
        try:
            data = _get(f"/{media_id}/insights", {"metric": "shares"})
            for item in data.get("data", []):
                if item.get("name") == "shares":
                    shares[media_id] = item.get("values", [{}])[0].get("value", 0)
        except requests.exceptions.HTTPError:
            shares[media_id] = 0
    return shares


def get_engagement_rate(media: list[dict], followers: int, shares: dict = None) -> float:
    """
    Calculate engagement rate using the industry-standard formula:
    average(Likes + Comments) per post ÷ Followers × 100

    This matches the methodology used by Sprout Social, Hootsuite, Later,
    and most benchmarking tools, enabling direct comparison against published
    industry averages (typically 1–3% for mid-tier accounts on Instagram).

    Args:
        media: List of post dicts from get_media.
        followers: Follower count from get_profile.

    Returns:
        Engagement rate as a percentage (e.g. 3.4 means 3.4%).
    """
    if not media or followers == 0:
        return 0.0
    total = sum(
        p.get("like_count", 0) + p.get("comments_count", 0)
        for p in media
    )
    avg = total / len(media)
    return round(avg / followers * 100, 2)


# ── Pipeline ──────────────────────────────────────────────────────────────────

def collect(account_name: str = None) -> dict:
    """
    Run the full Instagram data collection and cache results.

    Args:
        account_name: Slug used for the cache folder. Defaults to the account name
                      returned by the API.

    Returns:
        Combined dict with profile, media, insights, and engagement_rate.
    """
    profile = get_profile()
    user_id = profile["id"]
    name = account_name or profile.get("name", user_id)

    media = get_media(user_id)
    shares = get_media_shares(media)
    insights = get_insights(user_id)
    engagement_rate = get_engagement_rate(media, profile["followers_count"], shares)

    raw = {
        "profile": profile,
        "media": media,
        "shares": shares,
        "insights": insights,
        "engagement_rate": engagement_rate,
    }
    _cache(name, raw)
    return raw


# ── CLI summary ───────────────────────────────────────────────────────────────

def _print_summary(data: dict) -> None:
    from tabulate import tabulate
    profile = data["profile"]
    insights = data["insights"]

    print("\n── Profile ──────────────────────────────────────")
    print(tabulate(
        [
            ["Name", profile.get("name")],
            ["Followers", f"{profile.get('followers_count', 0):,}"],
            ["Website", profile.get("website") or "—"],
            ["Bio", (profile.get("biography") or "")[:80]],
        ],
        tablefmt="plain",
    ))

    print("\n── Monthly Insights ─────────────────────────────")
    print(tabulate(
        [
            ["Reach", f"{insights.get('reach', 0):,}"],
            ["Profile Views", f"{insights.get('profile_views', 0):,}"],
            ["Accounts Engaged", f"{insights.get('accounts_engaged', 0):,}"],
            ["Total Interactions", f"{insights.get('total_interactions', 0):,}"],
            ["Views", f"{insights.get('views', 0):,}"],
            ["Engagement Rate", f"{data['engagement_rate']}%"],
        ],
        tablefmt="plain",
    ))

    media = data["media"]
    if media:
        print("\n── Last 20 Posts ────────────────────────────────")
        rows = [
            [
                p.get("timestamp", "")[:10],
                p.get("media_type", ""),
                p.get("like_count", 0),
                p.get("comments_count", 0),
                (p.get("caption") or "")[:60],
            ]
            for p in media
        ]
        print(tabulate(rows, headers=["Date", "Type", "Likes", "Comments", "Caption"], tablefmt="rounded_outline"))

    print()


if __name__ == "__main__":
    if not ACCESS_TOKEN:
        print("Error: IG_ACCESS_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)

    print("Fetching Instagram data...")
    result = collect()
    _print_summary(result)
    print(f"Cached to data/communities/{result['profile'].get('name')}/instagram.json")
