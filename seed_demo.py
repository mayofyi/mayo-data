"""
Demo seed script — creates 4 brand accounts, one per brief.

Usage:
    python seed_demo.py                          # uses RENDER_URL from .env
    python seed_demo.py https://your-app.com     # or pass URL directly

The script is idempotent-ish: if a brand email already exists it will
log in instead of re-registering, then create the brief.

Brands:
  FORM Athletic      — Run Series Sponsorship
  Daily Ritual       — New Product Seeding
  Apex Outdoors      — Event Activation Pop-Up
  Motion Studios     — Ambassador Content Program
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("RENDER_URL", "http://localhost:5000")).rstrip("/")

# ── Brands + their briefs ────────────────────────────────────────────────────

PAIRS = [
    # ── 1. FORM Athletic — Sponsorship ──────────────────────────────────────
    (
        {
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
        },
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
            "deliverables": [
                "2× co-branded social posts per event featuring FORM product",
                "1× event recap reel or story set posted within 48 hours",
                "FORM branding visible at event (banners, kit on leaders)",
                "Monthly attendance report — number of participants, photos",
            ],
            "looking_for": (
                "Communities that run regular in-person events. We care more about "
                "consistency and culture than follower count. Tell us about your events — "
                "how often, how many people, what the vibe is."
            ),
        },
    ),

    # ── 2. Daily Ritual — Product Seeding ───────────────────────────────────
    (
        {
            "name": "Daily Ritual",
            "email": "demo@dailyritual.co",
            "password": "mayo-demo-2024",
            "tagline": "Made for the everyday athlete.",
            "bio": (
                "Daily Ritual makes clean, functional wellness supplements for people who "
                "train consistently and live intentionally. No hype, no proprietary blends — "
                "just transparent formulas that actually work. We're not for the competitor "
                "chasing PRs once a year. We're for the person who shows up every day."
            ),
            "website": "https://dailyritual.co",
            "category": "Wellness & Supplements",
            "color": "#f97316",
            "gradient": "linear-gradient(135deg, #1a0800 0%, #3d1a00 40%, #7a3500 70%, #f97316 100%)",
            "initial": "D",
        },
        {
            "title": "New Product Seeding — Daily Ritual Core Launch",
            "partnership_type": "Product Partnership",
            "goal": (
                "We're launching our Core Collection in May — our cleanest, most "
                "versatile performance nutrition line yet. Before we go wide, we want it "
                "used by real communities. We'll send product to community leaders and a "
                "handful of members, then ask for honest feedback and a few organic posts. "
                "No scripts. Just real people using real products."
            ),
            "campaign_goal": "Product launch — seeding and authentic social proof",
            "budget": "800",
            "budget_period": "Per community (product value + fee)",
            "deadline": "Apr 15 2025",
            "activation_window": "May 2025 (launch month)",
            "tags": ["Product Launch", "Seeding", "Fitness", "Wellness", "Nutrition"],
            "kpis": ["Posts tagged #DailyRitualCore", "Stories / UGC pieces", "Honest feedback submitted"],
            "products": [
                {"name": "Daily Ritual Core Stack", "description": "Pre-workout + recovery bundle, gifted to 5–8 community members"},
                {"name": "DR Shaker + Tote", "description": "Branded gear gifted alongside product"},
            ],
            "requirements": {
                "min_active_members": 100,
                "location": "US",
                "instagram_connected": True,
            },
            "deliverables": [
                "3–5 Instagram posts or stories per member using #DailyRitualCore",
                "Short written or voice-note feedback on each product (via a simple form)",
                "At least 1 group post or recap showing product in a training context",
            ],
            "looking_for": (
                "Communities whose members actually train. We want the product used on "
                "runs, at group workouts, and on rest days — not just photographed. "
                "Engagement matters more than reach. Micro-communities welcome."
            ),
        },
    ),

    # ── 3. Apex Outdoors — Event Activation ─────────────────────────────────
    (
        {
            "name": "Apex Outdoors",
            "email": "demo@apexoutdoors.co",
            "password": "mayo-demo-2024",
            "tagline": "Gear built for where you go.",
            "bio": (
                "Apex Outdoors designs technical gear for people who take their weekends "
                "seriously. Hiking, trail running, urban cycling, open water — if you're "
                "moving through the outdoors with purpose, our gear is built for you. "
                "We believe the best way to earn a community's trust is to show up in "
                "their world, not just their feed."
            ),
            "website": "https://apexoutdoors.co",
            "category": "Outdoor & Adventure Gear",
            "color": "#22c55e",
            "gradient": "linear-gradient(135deg, #001a08 0%, #003d14 40%, #006b25 70%, #22c55e 100%)",
            "initial": "A",
        },
        {
            "title": "Event Activation Partnership — Apex Pop-Up",
            "partnership_type": "Event Partnership",
            "goal": (
                "We want to show up at your events. Apex will bring product samples, "
                "a branded pop-up setup, and a photographer. Your community gets a better "
                "event experience; we get real content and direct community exposure. "
                "We'll cover all activation costs — you just give us a slot."
            ),
            "campaign_goal": "Direct community engagement and content capture",
            "budget": "1500",
            "budget_period": "Per activation",
            "deadline": "Ongoing — 3 weeks lead time needed",
            "activation_window": "May–Aug 2025",
            "tags": ["Events", "Activation", "Pop-Up", "Outdoor", "IRL"],
            "kpis": ["Attendees reached", "Pieces of content captured", "Social tags on event day"],
            "products": [
                {"name": "Apex Sample Kit", "description": "Gear samples available for attendees to try"},
                {"name": "Activation Setup", "description": "Branded pop-up, signage, and photography provided by Apex"},
            ],
            "requirements": {
                "min_active_members": 80,
                "location": "Los Angeles, New York, Austin, Chicago, Denver (or pitch us your city)",
                "event_size": "50+ attendees per event",
            },
            "deliverables": [
                "Minimum 60-minute pop-up slot at one upcoming event",
                "2–3 social tags on event day using #ApexActivation",
                "Post-event photo set shared with Apex (10+ usable shots)",
            ],
            "looking_for": (
                "Communities with regular in-person gatherings where people actually "
                "show up. Group runs, fitness classes, wellness markets, outdoor clubs — "
                "anything with a real crowd. Tell us about your biggest upcoming event."
            ),
        },
    ),

    # ── 4. Motion Studios — Content Partnership ──────────────────────────────
    (
        {
            "name": "Motion Studios",
            "email": "demo@motionstudios.co",
            "password": "mayo-demo-2024",
            "tagline": "Move. Create. Repeat.",
            "bio": (
                "Motion Studios is a fitness lifestyle brand built around content — we "
                "make training gear, apparel, and accessories designed to look as good on "
                "camera as they perform in the gym. We work with communities who already "
                "create, already show up, and already have a voice. We don't manufacture "
                "content — we amplify the content that's already happening."
            ),
            "website": "https://motionstudios.co",
            "category": "Fitness Lifestyle & Content",
            "color": "#8b5cf6",
            "gradient": "linear-gradient(135deg, #0d0014 0%, #1e0033 40%, #3b0066 70%, #8b5cf6 100%)",
            "initial": "M",
        },
        {
            "title": "Ambassador Content Program — Quarterly Partnership",
            "partnership_type": "Content Partnership",
            "goal": (
                "We're building a library of authentic community-generated content for "
                "Motion's social channels and website. This isn't a one-off collab — we "
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
                {"name": "Seasonal Motion Kit", "description": "Full seasonal collection gifted to community leader and up to 3 featured members"},
                {"name": "Content Brief", "description": "Monthly creative direction — loose enough to stay authentic"},
            ],
            "requirements": {
                "min_active_members": 200,
                "instagram_followers": "1,000+ on community account",
                "content_cadence": "Able to produce 4+ pieces of content per month",
            },
            "deliverables": [
                "4× Instagram posts or reels per month featuring Motion product",
                "1× 60-second video per quarter for Motion's owned channels",
                "Monthly content pack: 10+ stills delivered via shared drive",
                "Quarterly Zoom check-in with Motion content team",
            ],
            "looking_for": (
                "Communities that already post regularly and have a clear visual identity. "
                "We don't want to manufacture your content — we want to be a natural part "
                "of it. Show us your last 9 posts and we'll know within 30 seconds if "
                "it's a fit."
            ),
        },
    ),
]

# ── Script ─────────────────────────────────────────────────────────────────────

def register_or_login(brand):
    reg_resp = requests.post(f"{BASE_URL}/api/register/brand", json=brand, timeout=15)
    if reg_resp.status_code == 409:
        print(f"  {brand['name']} already exists — logging in.")
        login_resp = requests.post(f"{BASE_URL}/api/login", json={
            "email": brand["email"],
            "password": brand["password"],
        }, timeout=15)
        login_resp.raise_for_status()
        return login_resp.json()["token"]
    elif reg_resp.ok:
        print(f"  Registered {brand['name']} ({brand['email']})")
        return reg_resp.json()["token"]
    else:
        print(f"  ERROR registering {brand['name']}: {reg_resp.status_code} — {reg_resp.text}")
        return None


def main():
    print(f"Target: {BASE_URL}\n")

    for brand, brief in PAIRS:
        print(f"\n── {brand['name']} ──────────────────────────────────────────────")
        token = register_or_login(brand)
        if not token:
            continue

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(f"{BASE_URL}/api/briefs", json=brief, headers=headers, timeout=15)
        if resp.ok:
            print(f"  ✓ Brief created: {brief['title']}")
        else:
            print(f"  ✗ Brief failed: {resp.status_code}: {resp.text}")

    print("\n── Done ──────────────────────────────────────────────────────────")
    print("Community users will see all 4 briefs from different brands in Discover.\n")
    print("Brand logins:")
    for brand, _ in PAIRS:
        print(f"  {brand['name']:20s}  {brand['email']}  /  {brand['password']}")
    print()


if __name__ == "__main__":
    main()
