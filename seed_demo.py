"""
Demo seed script — creates brands, briefs, communities, and projects.

Usage:
    python3 seed_demo.py                          # uses RENDER_URL from .env
    python3 seed_demo.py https://your-app.com     # or pass URL directly

Idempotent-ish: brands skip registration if email already exists.
Communities are always created fresh (no duplicate check).

Seeds:
  Brands & briefs:  FORM Athletic, Daily Ritual, Apex Outdoors, Motion Studios
  Communities:      Concrete Run Collective, Sunday Social Club, The Grind Collective
  Projects:         4 cross-linked projects across all statuses
"""

import sys
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("RENDER_URL", "http://localhost:5000")).rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "mayo-admin")
ADMIN_HEADERS = {"X-Admin-Token": ADMIN_TOKEN, "Content-Type": "application/json"}


# ── Brands + their briefs ────────────────────────────────────────────────────

PAIRS = [
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
                "every week because they love it."
            ),
            "website": "https://formsports.co",
            "category": "Activewear & Performance",
            "color": "#00c4a7",
            "initial": "F",
        },
        {
            "title": "Community Run Series — Season Sponsorship",
            "partnership_type": "Sponsorship",
            "campaign_goal": "Brand awareness and community association",
            "budget": "2500",
            "looking_for": (
                "Communities that run regular in-person events. We care more about "
                "consistency and culture than follower count."
            ),
            "tags": ["Running", "Fitness", "Events", "Sponsorship"],
        },
    ),
    (
        {
            "name": "Daily Ritual",
            "email": "demo@dailyritual.co",
            "password": "mayo-demo-2024",
            "tagline": "Made for the everyday athlete.",
            "bio": (
                "Daily Ritual makes clean, functional wellness supplements for people who "
                "train consistently and live intentionally. No hype, no proprietary blends — "
                "just transparent formulas that actually work."
            ),
            "website": "https://dailyritual.co",
            "category": "Wellness & Supplements",
            "color": "#f97316",
            "initial": "D",
        },
        {
            "title": "New Product Seeding — Daily Ritual Core Launch",
            "partnership_type": "Product Partnership",
            "campaign_goal": "Product launch — seeding and authentic social proof",
            "budget": "800",
            "looking_for": (
                "Communities whose members actually train. Engagement matters more than reach. "
                "Micro-communities welcome."
            ),
            "tags": ["Product Launch", "Seeding", "Fitness", "Wellness"],
        },
    ),
    (
        {
            "name": "Apex Outdoors",
            "email": "demo@apexoutdoors.co",
            "password": "mayo-demo-2024",
            "tagline": "Gear built for where you go.",
            "bio": (
                "Apex Outdoors designs technical gear for people who take their weekends "
                "seriously. Hiking, trail running, urban cycling, open water — if you're "
                "moving through the outdoors with purpose, our gear is built for you."
            ),
            "website": "https://apexoutdoors.co",
            "category": "Outdoor & Adventure Gear",
            "color": "#22c55e",
            "initial": "A",
        },
        {
            "title": "Event Activation Partnership — Apex Pop-Up",
            "partnership_type": "Event Partnership",
            "campaign_goal": "Direct community engagement and content capture",
            "budget": "1500",
            "looking_for": (
                "Communities with regular in-person gatherings. Group runs, fitness classes, "
                "wellness markets, outdoor clubs — anything with a real crowd."
            ),
            "tags": ["Events", "Activation", "Pop-Up", "Outdoor"],
        },
    ),
    (
        {
            "name": "Motion Studios",
            "email": "demo@motionstudios.co",
            "password": "mayo-demo-2024",
            "tagline": "Move. Create. Repeat.",
            "bio": (
                "Motion Studios is a fitness lifestyle brand built around content. We work "
                "with communities who already create, already show up, and already have a voice. "
                "We don't manufacture content — we amplify what's already happening."
            ),
            "website": "https://motionstudios.co",
            "category": "Fitness Lifestyle & Content",
            "color": "#8b5cf6",
            "initial": "M",
        },
        {
            "title": "Ambassador Content Program — Quarterly Partnership",
            "partnership_type": "Content Partnership",
            "campaign_goal": "Ongoing authentic content for owned channels",
            "budget": "3000",
            "looking_for": (
                "Communities that already post regularly and have a clear visual identity. "
                "Show us your last 9 posts and we'll know within 30 seconds if it's a fit."
            ),
            "tags": ["Content", "UGC", "Social Media", "Ambassador"],
        },
    ),
]


# ── Demo communities ─────────────────────────────────────────────────────────

COMMUNITIES = [
    {
        "name": "Concrete Run Collective",
        "tagline": "New York's early morning run crew.",
        "location": "New York, NY",
        "description": (
            "We're 400+ runners who meet before the city wakes up. Started as a "
            "Tuesday 6am loop around the park, now we run 4 days a week, host monthly "
            "races, and have members in every borough. No pace requirement, no drama — "
            "just people who love running and the community that comes with it."
        ),
        "active_members": 420,
        "tags": ["Running", "Events", "NYC", "Fitness", "Community"],
        "archetype": "loyalists",
        "cover_option": 3,
    },
    {
        "name": "Sunday Social Club",
        "tagline": "Wellness, movement, and good company — every Sunday.",
        "location": "Los Angeles, CA",
        "description": (
            "Sunday Social is a weekly gathering in Silver Lake that started as a "
            "yoga class and grew into something harder to define. We do movement, we do "
            "coffee, we do farmers markets, and we do long brunches. Our members are "
            "designers, trainers, chefs, musicians — people who care about how they live."
        ),
        "active_members": 280,
        "tags": ["Wellness", "Lifestyle", "LA", "Events", "Yoga"],
        "archetype": "evangelists",
        "cover_option": 5,
    },
    {
        "name": "The Grind Collective",
        "tagline": "Chicago's independent gym and training community.",
        "location": "Chicago, IL",
        "description": (
            "The Grind is a collective of independent trainers, gym owners, and serious "
            "athletes across Chicago. We run monthly competitions, open gym sessions, and "
            "a mentorship programme for up-and-coming coaches. Not a franchise, not a brand — "
            "a community that builds each other up."
        ),
        "active_members": 190,
        "tags": ["Fitness", "Strength", "Chicago", "Training", "Community"],
        "archetype": "buyers",
        "cover_option": 2,
    },
]


# ── Script ───────────────────────────────────────────────────────────────────

def register_or_login(brand):
    resp = requests.post(f"{BASE_URL}/api/register/brand", json=brand, timeout=15)
    if resp.status_code == 409:
        print(f"  {brand['name']} already registered — logging in.")
        login = requests.post(f"{BASE_URL}/api/login", json={"email": brand["email"], "password": brand["password"]}, timeout=15)
        login.raise_for_status()
        return login.json()["token"], login.json().get("user", {}).get("id")
    elif resp.ok:
        print(f"  Registered {brand['name']}")
        return resp.json()["token"], resp.json().get("user", {}).get("id")
    else:
        print(f"  ERROR {brand['name']}: {resp.status_code} — {resp.text[:120]}")
        return None, None


def create_community(comm):
    resp = requests.post(f"{BASE_URL}/api/community", json=comm, timeout=15)
    if resp.ok:
        cid = resp.json()["id"]
        print(f"  Created community: {comm['name']} ({cid[:8]}…)")
        # Set archetype via admin update
        if comm.get("archetype"):
            requests.put(
                f"{BASE_URL}/api/community/{cid}",
                json={"archetype": comm["archetype"], "archetype_source": "manual"},
                timeout=15,
            )
        return cid
    else:
        print(f"  ERROR creating {comm['name']}: {resp.status_code} — {resp.text[:120]}")
        return None


def create_project(community_id, brand_id, brief_id, title, ptype, budget, status, start, end):
    resp = requests.post(
        f"{BASE_URL}/api/admin/projects?token={ADMIN_TOKEN}",
        json={
            "community_id": community_id,
            "brand_id": brand_id,
            "brief_id": brief_id,
            "title": title,
            "type": ptype,
            "budget": budget,
            "status": status,
            "start_date": start,
            "end_date": end,
        },
        headers=ADMIN_HEADERS,
        timeout=15,
    )
    if resp.ok:
        pid = resp.json()["id"]
        print(f"  Created project [{status}]: {title} ({pid[:8]}…)")
        return pid
    else:
        print(f"  ERROR creating project: {resp.status_code} — {resp.text[:120]}")
        return None


def main():
    print(f"Target: {BASE_URL}\n")

    # ── Brands & briefs ──────────────────────────────────────────────────────
    print("── Brands & Briefs ────────────────────────────────────────────────")
    brand_ids = {}
    brief_ids = {}

    for brand_data, brief_data in PAIRS:
        print(f"\n  {brand_data['name']}")
        token, brand_id = register_or_login(brand_data)
        if not token:
            continue
        brand_ids[brand_data["name"]] = brand_id

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = requests.post(f"{BASE_URL}/api/briefs", json=brief_data, headers=headers, timeout=15)
        if resp.ok:
            brief_ids[brand_data["name"]] = resp.json().get("id")
            print(f"  ✓ Brief: {brief_data['title']}")
        else:
            print(f"  ✗ Brief failed: {resp.status_code} — {resp.text[:120]}")

    # ── Communities ──────────────────────────────────────────────────────────
    print("\n── Communities ────────────────────────────────────────────────────")
    community_ids = {}
    for comm in COMMUNITIES:
        cid = create_community(comm)
        if cid:
            community_ids[comm["name"]] = cid

    # ── Projects ─────────────────────────────────────────────────────────────
    print("\n── Projects ───────────────────────────────────────────────────────")

    if community_ids.get("Concrete Run Collective") and brand_ids.get("FORM Athletic"):
        create_project(
            community_id=community_ids["Concrete Run Collective"],
            brand_id=brand_ids["FORM Athletic"],
            brief_id=brief_ids.get("FORM Athletic"),
            title="Run Series — Spring Season",
            ptype="Sponsorship",
            budget=2500,
            status="active",
            start="2025-04-01",
            end="2025-09-30",
        )

    if community_ids.get("Sunday Social Club") and brand_ids.get("Daily Ritual"):
        create_project(
            community_id=community_ids["Sunday Social Club"],
            brand_id=brand_ids["Daily Ritual"],
            brief_id=brief_ids.get("Daily Ritual"),
            title="Core Collection Launch Seeding",
            ptype="Product Partnership",
            budget=800,
            status="complete",
            start="2025-05-01",
            end="2025-05-31",
        )

    if community_ids.get("The Grind Collective") and brand_ids.get("Apex Outdoors"):
        create_project(
            community_id=community_ids["The Grind Collective"],
            brand_id=brand_ids["Apex Outdoors"],
            brief_id=brief_ids.get("Apex Outdoors"),
            title="Chicago Pop-Up Activation",
            ptype="Event Partnership",
            budget=1500,
            status="contracted",
            start="2025-06-14",
            end="2025-06-14",
        )

    if community_ids.get("Concrete Run Collective") and brand_ids.get("Motion Studios"):
        create_project(
            community_id=community_ids["Concrete Run Collective"],
            brand_id=brand_ids["Motion Studios"],
            brief_id=brief_ids.get("Motion Studios"),
            title="Q2 Ambassador Content Partnership",
            ptype="Content Partnership",
            budget=3000,
            status="scoping",
            start="2025-07-01",
            end="2025-09-30",
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n── Done ───────────────────────────────────────────────────────────")
    print("Brand logins:")
    for brand_data, _ in PAIRS:
        print(f"  {brand_data['name']:22s}  {brand_data['email']}  /  {brand_data['password']}")
    print()


if __name__ == "__main__":
    main()
