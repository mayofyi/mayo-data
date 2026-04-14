"""
Demo seed script — creates one brand account and 4 open briefs.

Usage:
    python seed_demo.py                          # uses RENDER_URL from .env
    python seed_demo.py https://your-app.com     # or pass URL directly

The script is idempotent-ish: if the brand email already exists it will
log in instead of re-registering, then create the briefs.
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("RENDER_URL", "http://localhost:5000")).rstrip("/")

# ── Demo brand ─────────────────────────────────────────────────────────────────

BRAND = {
    "name": "FORM Athletic",
    "email": "demo@formsports.co",
    "password": "mayo-demo-2024",
    "tagline": "Built for the way you move.",
    "bio": (
        "FORM Athletic makes performance apparel and gear for people who move — "
        "runners, gym-goers, weekend warriors. We don't chase elite athletes. We "
        "chase the 6am run club, the garage gym crew, the people who show up "
        "every week because they love it. We partner with communities because that's "
        "where authentic culture lives."
    ),
    "website": "https://formsports.co",
    "category": "Activewear & Performance",
    "color": "#00c4a7",
    "gradient": "linear-gradient(135deg, #001a17 0%, #003d33 40%, #006b5a 70%, #00c4a7 100%)",
    "initial": "F",
}

# ── 4 open briefs ──────────────────────────────────────────────────────────────

BRIEFS = [
    {
        "title": "Community Run Series — Season Sponsorship",
        "partnership_type": "Sponsorship",
        "goal": (
            "We're looking for 3–5 running or fitness communities to sponsor for "
            "a full season. This means FORM co-branding at your events, product "
            "gifting for your members, and a small budget for content capture. "
            "We want to show up where real runners show up — not billboards."
        ),
        "campaign_goal": "Brand awareness and community association",
        "budget": "2500",
        "budget_period": "Per quarter",
        "deadline": "Rolling — apply any time",
        "activation_window": "Q2–Q3 2025 (Apr–Sep)",
        "tags": ["Running", "Fitness", "Events", "Sponsorship"],
        "kpis": ["Event attendance reach", "Co-branded content pieces", "Member product adoption"],
        "products": [
            {"name": "FORM Run Kit", "description": "Technical shorts + top, gifted to community leaders and key members"},
            {"name": "FORM Event Pack", "description": "Branded banners, finish-line tape, reusable cups for event activation"},
        ],
        "requirements": {
            "min_active_members": 150,
            "location": "US",
            "events_per_month": "At least 1 regular group event (run, workout, meetup)",
        },
        "looking_for": (
            "Communities that run regular in-person events. We care more about "
            "consistency and culture than follower count. Tell us about your events — "
            "how often, how many people, what the vibe is."
        ),
    },
    {
        "title": "New Product Seeding — FORM Core Collection Launch",
        "partnership_type": "Product Partnership",
        "goal": (
            "We're launching the FORM Core Collection in May — our cleanest, most "
            "versatile performance line yet. Before we go wide, we want it worn by "
            "real communities. We'll send product to community leaders and a handful "
            "of members, then ask for honest feedback and a few organic posts. "
            "No scripts. Just real people wearing real gear."
        ),
        "campaign_goal": "Product launch — seeding and authentic social proof",
        "budget": "800",
        "budget_period": "Per community (product value + fee)",
        "deadline": "Apr 15 2025",
        "activation_window": "May 2025 (launch month)",
        "tags": ["Product Launch", "Seeding", "Fitness", "Wellness", "Apparel"],
        "kpis": ["Posts tagged #FORMcore", "Stories / UGC pieces", "Honest feedback submitted"],
        "products": [
            {"name": "FORM Core Shorts", "description": "5\" and 7\" inseam options, gifted to 5–8 community members"},
            {"name": "FORM Core Top", "description": "Lightweight training tee, gifted alongside shorts"},
        ],
        "requirements": {
            "min_active_members": 100,
            "location": "US",
            "instagram_connected": True,
        },
        "looking_for": (
            "Communities whose members actually train. We want the gear worn on "
            "runs, in the gym, at group workouts — not styled in a flat-lay. "
            "Engagement matters more than reach. Micro-communities welcome."
        ),
    },
    {
        "title": "Event Activation Partnership — FORM Pop-Up",
        "partnership_type": "Event Partnership",
        "goal": (
            "We want to show up at your events. FORM will bring product samples, "
            "a branded pop-up setup, and a photographer/videographer. Your community "
            "gets a better event experience; we get real content and direct community "
            "exposure. We'll cover all activation costs — you just give us a slot."
        ),
        "campaign_goal": "Direct community engagement and content capture",
        "budget": "1500",
        "budget_period": "Per activation",
        "deadline": "Ongoing — 3 weeks lead time needed",
        "activation_window": "May–Aug 2025",
        "tags": ["Events", "Activation", "Pop-Up", "Fitness", "IRL"],
        "kpis": ["Attendees reached", "Pieces of content captured", "Social tags on event day"],
        "products": [
            {"name": "FORM Sample Kit", "description": "Product samples available for attendees to try"},
            {"name": "Activation Setup", "description": "Branded pop-up, signage, and photography provided by FORM"},
        ],
        "requirements": {
            "min_active_members": 80,
            "location": "Los Angeles, New York, Austin, Chicago, Denver (or pitch us your city)",
            "event_size": "50+ attendees per event",
        },
        "looking_for": (
            "Communities with regular in-person gatherings where people actually "
            "show up. Group runs, fitness classes, wellness markets, sports leagues — "
            "anything with a real crowd. Tell us about your biggest upcoming event."
        ),
    },
    {
        "title": "Ambassador Content Program — Quarterly Partnership",
        "partnership_type": "Content Partnership",
        "goal": (
            "We're building a library of authentic community-generated content for "
            "FORM's social channels and website. This isn't a one-off collab — we "
            "want ongoing partners who produce real content as part of their normal "
            "community life. Monthly check-ins, quarterly deliverables, and a "
            "longer-term relationship if it's working."
        ),
        "campaign_goal": "Ongoing authentic content for owned channels",
        "budget": "3000",
        "budget_period": "Per quarter",
        "deadline": "Rolling intake — next cohort starts May 1",
        "activation_window": "Q2 2025 onwards (renewable quarterly)",
        "tags": ["Content", "UGC", "Social Media", "Ambassador", "Lifestyle"],
        "kpis": ["Content pieces delivered per month", "Instagram reach from posts", "Content quality score (internal)"],
        "products": [
            {"name": "Seasonal FORM Kit", "description": "Full seasonal collection gifted to community leader and up to 3 featured members"},
            {"name": "Content Brief", "description": "Monthly creative direction — loose enough to stay authentic"},
        ],
        "requirements": {
            "min_active_members": 200,
            "instagram_followers": "1,000+ on community account",
            "content_cadence": "Able to produce 4+ pieces of content per month",
        },
        "looking_for": (
            "Communities that already post regularly and have a clear visual identity. "
            "We don't want to manufacture your content — we want to be a natural part "
            "of it. Show us your last 9 posts and we'll know within 30 seconds if "
            "it's a fit."
        ),
    },
]

# ── Script ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Target: {BASE_URL}\n")

    # 1. Register brand (or login if already exists)
    print("Creating brand account…")
    reg_resp = requests.post(f"{BASE_URL}/api/register/brand", json=BRAND, timeout=15)

    if reg_resp.status_code == 409:
        print("  Brand already exists — logging in instead.")
        login_resp = requests.post(f"{BASE_URL}/api/login", json={
            "email": BRAND["email"],
            "password": BRAND["password"],
        }, timeout=15)
        login_resp.raise_for_status()
        token = login_resp.json()["token"]
        print(f"  Logged in as {BRAND['name']}")
    elif reg_resp.ok:
        token = reg_resp.json()["token"]
        print(f"  Registered {BRAND['name']} ({BRAND['email']})")
    else:
        print(f"  ERROR: {reg_resp.status_code} — {reg_resp.text}")
        sys.exit(1)

    # 2. Create briefs
    print(f"\nCreating {len(BRIEFS)} briefs…")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for i, brief in enumerate(BRIEFS, 1):
        resp = requests.post(f"{BASE_URL}/api/briefs", json=brief, headers=headers, timeout=15)
        if resp.ok:
            print(f"  ✓ [{i}/{len(BRIEFS)}] {brief['title']}")
        else:
            print(f"  ✗ [{i}/{len(BRIEFS)}] {brief['title']} — {resp.status_code}: {resp.text}")

    print(f"\nDone. Log in to the app as a brand:")
    print(f"  Email:    {BRAND['email']}")
    print(f"  Password: {BRAND['password']}")
    print(f"\nCommunity users will see all 4 briefs in Discover.\n")


if __name__ == "__main__":
    main()
