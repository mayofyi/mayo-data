"""
Mayo — Flask app
Serves the community onboarding flow, handles Instagram OAuth,
stores community profiles in PostgreSQL, and runs the data pipeline.
"""

import base64
import hashlib
import hmac
import json as _json_stdlib
import math
import os
import threading
import time
import uuid

import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request

load_dotenv()

META_APP_ID = os.getenv("META_APP_ID")
META_APP_SECRET = os.getenv("META_APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "mayo-admin")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "mayo-secret-key-change-in-production")


# ── Auth utilities ─────────────────────────────────────────────────────────────

def hash_password(password):
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt + key).decode()


def verify_password(password, stored):
    try:
        decoded = base64.b64decode(stored.encode())
        salt, key = decoded[:16], decoded[16:]
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return hmac.compare_digest(key, check)
    except Exception:
        return False


def create_token(payload):
    payload = {**payload, "iat": int(time.time())}
    encoded = base64.b64encode(_json_stdlib.dumps(payload).encode()).decode()
    sig = hmac.new(SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{sig}"


def verify_token(token):
    try:
        encoded, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        return _json_stdlib.loads(base64.b64decode(encoded).decode())
    except Exception:
        return None


def require_auth(req):
    """Return token payload or raise 401."""
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return verify_token(auth[7:])
STORAGE_BUCKET = "mayo-assets"

# ── Metric calculation utilities ───────────────────────────────────────────────

# Bucket-based follower tiers for NM (Option 3 — no individual API lookups needed)
TIER_DATA = {
    "micro": {"followers": 5_500,   "er": 5.0},
    "mid":   {"followers": 55_000,  "er": 3.0},
    "macro": {"followers": 300_000, "er": 1.5},
}


def calculate_nm(members, active_members):
    """Network Multiplier. Prefers actual ig_followers/ig_er over tier midpoints.
    Only Mayo-verified members contribute."""
    if not active_members:
        return None
    eligible = [
        m for m in (members or [])
        if m.get("verified") and (m.get("ig_followers") or m.get("follower_tier") in TIER_DATA)
    ]
    if not eligible:
        return None
    total = 0.0
    for m in eligible:
        followers = m.get("ig_followers") or TIER_DATA.get(m.get("follower_tier", ""), {}).get("followers", 0)
        er = m.get("ig_er") or TIER_DATA.get(m.get("follower_tier", ""), {}).get("er", 3.0)
        if followers:
            total += math.log(followers + 1) * er
    return round(total / active_members, 2)


def calculate_gv(snapshots):
    """Growth Velocity: follower % change over the most recent ≥90-day window → 0-100."""
    if not snapshots or len(snapshots) < 2:
        return None
    from datetime import datetime
    sorted_snaps = sorted(snapshots, key=lambda s: s.get("captured_at", ""))
    latest = sorted_snaps[-1]
    try:
        latest_ts = datetime.fromisoformat(latest["captured_at"].replace("Z", "+00:00")).timestamp()
    except Exception:
        return None
    cutoff = latest_ts - 90 * 86400
    baseline = None
    for s in sorted_snaps[:-1]:
        try:
            ts = datetime.fromisoformat(s["captured_at"].replace("Z", "+00:00")).timestamp()
            if ts <= cutoff:
                baseline = s
        except Exception:
            continue
    if not baseline:
        return None
    base_f = baseline.get("followers") or 0
    if not base_f:
        return None
    growth_pct = (latest.get("followers", 0) - base_f) / base_f * 100
    # 0% growth → 30, 10% → ~53, 30%+ → 100, declining → 0–29
    return min(100, max(0, round(30 + growth_pct * 2.33)))


def calculate_bah(case_studies):
    """Brand Association History score from verified case studies."""
    TIER_WEIGHTS = {"tier1": 20, "tier2": 12, "tier3": 6}
    verified = [cs for cs in (case_studies or []) if cs.get("verified")]
    if not verified:
        return 0
    return min(100, sum(TIER_WEIGHTS.get(cs.get("brand_tier", "tier2"), 12) for cs in verified))


def calculate_pmm(press_mentions):
    """Press & Media Mentions score from admin-confirmed articles."""
    OUTLET_WEIGHTS = {"national": 25, "regional": 12, "niche": 6, "unknown": 3}
    confirmed = [m for m in (press_mentions or []) if m.get("confirmed") is True]
    if not confirmed:
        return 0
    return min(100, sum(OUTLET_WEIGHTS.get(m.get("outlet_tier", "unknown"), 3) for m in confirmed))


def parse_claude_json(text):
    """Parse JSON from a Claude response, stripping markdown code fences if present."""
    import json as _json
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty response from AI")
    # Strip ```json ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line if it's ```
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner).strip()
    return _json.loads(text)


def calculate_cis_raw(miq, gv, bah, pmm):
    """Weighted average of CIS sub-scores. Rebalances automatically when inputs are missing."""
    inputs = [(miq, 0.25), (gv, 0.25), (bah, 0.25), (pmm, 0.25)]
    scored = [(score, w) for score, w in inputs if score is not None]
    if not scored:
        return None
    total_weight = sum(w for _, w in scored)
    return round(sum(score * w for score, w in scored) / total_weight)


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB upload limit

# Render uses postgres:// but psycopg2 requires postgresql://
_db_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url if "sslmode" in _db_url else _db_url + "?sslmode=require"


# ── Database ───────────────────────────────────────────────────────────────────

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS communities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tagline TEXT,
                    location TEXT,
                    description TEXT,
                    tags TEXT[],
                    active_members INTEGER,
                    website TEXT,
                    cover_option INTEGER DEFAULT 1,
                    cover_image_url TEXT,
                    leader_name TEXT,
                    email TEXT,
                    substack_url TEXT,
                    instagram_token TEXT,
                    instagram_user_id TEXT,
                    instagram_data JSONB,
                    instagram_connected_at TIMESTAMP,
                    substack_data JSONB,
                    notable_members JSONB DEFAULT '[]',
                    partnership_preferences TEXT,
                    capabilities TEXT[],
                    media_items JSONB DEFAULT '[]',
                    case_studies JSONB DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Brands table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS brands (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    tagline TEXT,
                    bio TEXT,
                    website TEXT,
                    category TEXT,
                    color TEXT DEFAULT '#888',
                    gradient TEXT,
                    initial TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Briefs table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS briefs (
                    id TEXT PRIMARY KEY,
                    brand_id TEXT REFERENCES brands(id),
                    title TEXT NOT NULL,
                    campaign_goal TEXT,
                    partnership_type TEXT,
                    budget TEXT,
                    budget_period TEXT,
                    tags TEXT[],
                    requirements JSONB DEFAULT '{}',
                    kpis JSONB DEFAULT '[]',
                    products JSONB DEFAULT '[]',
                    deliverables JSONB DEFAULT '[]',
                    deadline TEXT,
                    activation_window TEXT,
                    goal TEXT,
                    looking_for TEXT,
                    status TEXT DEFAULT 'open',
                    response_count INTEGER DEFAULT 0,
                    cover_image_url TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Projects table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    brief_id TEXT REFERENCES briefs(id),
                    community_id TEXT REFERENCES communities(id),
                    brand_id TEXT REFERENCES brands(id),
                    type TEXT,
                    budget NUMERIC,
                    stage INTEGER DEFAULT 0,
                    stages JSONB DEFAULT '[]',
                    timeline JSONB DEFAULT '[]',
                    milestones JSONB DEFAULT '[]',
                    logistics JSONB DEFAULT '{}',
                    payments JSONB DEFAULT '{}',
                    team JSONB DEFAULT '[]',
                    chat JSONB DEFAULT '[]',
                    status TEXT DEFAULT 'active',
                    start_date TEXT,
                    end_date TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Add new columns to existing tables
            for col, typedef in [
                ("cover_image_url", "TEXT"),
                ("media_items", "JSONB DEFAULT '[]'"),
                ("case_studies", "JSONB DEFAULT '[]'"),
                ("leader_name", "TEXT"),
                ("email", "TEXT"),
                ("notable_members", "JSONB DEFAULT '[]'"),
                ("partnership_preferences", "TEXT"),
                ("capabilities", "TEXT[]"),
                ("substack_data", "JSONB"),
                ("archetype", "TEXT"),
                ("archetype_source", "TEXT"),
                ("archetype_reasoning", "TEXT"),
                ("archetype_confidence", "INT"),
                ("network_multiplier", "FLOAT"),
                ("cis_raw", "INT"),
                ("cis_stamped", "INT"),
                ("cis_stamp_by", "TEXT"),
                ("cis_stamped_at", "TIMESTAMP"),
                ("cis_stamp_expires_at", "TIMESTAMP"),
                ("ig_snapshots", "JSONB DEFAULT '[]'"),
                ("press_mentions", "JSONB DEFAULT '[]'"),
                ("miq_score", "INT"),
                ("miq_reasoning", "TEXT"),
                ("password_hash", "TEXT"),
            ]:
                cur.execute(f"""
                    ALTER TABLE communities ADD COLUMN IF NOT EXISTS {col} {typedef}
                """)
            # Brands table migrations
            cur.execute("ALTER TABLE brands ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE")
            for col, typedef in [
                ("leader_name", "TEXT"),
                ("leader_role", "TEXT"),
                ("values", "TEXT"),
                ("looking_for", "TEXT"),
                ("social_links", "JSONB DEFAULT '{}'"),
                ("profile_image_url", "TEXT"),
                ("header_image_url", "TEXT"),
            ]:
                cur.execute(f"ALTER TABLE brands ADD COLUMN IF NOT EXISTS {col} {typedef}")
            # Briefs table migrations
            cur.execute("ALTER TABLE brands ADD COLUMN IF NOT EXISTS past_partnerships JSONB DEFAULT '[]'")
            cur.execute("ALTER TABLE briefs ADD COLUMN IF NOT EXISTS cover_image_url TEXT")
            cur.execute("ALTER TABLE briefs ADD COLUMN IF NOT EXISTS deliverables JSONB DEFAULT '[]'")
        conn.commit()


try:
    init_db()
except Exception as e:
    print(f"[db] Could not initialise database: {e}")


# ── Background pipeline ────────────────────────────────────────────────────────

def run_instagram_pipeline(community_id, token):
    try:
        import connectors.instagram as ig
        from datetime import datetime
        ig.ACCESS_TOKEN = token
        data = ig.collect()
        snapshot = {
            "followers": (data.get("profile") or {}).get("followers_count") or 0,
            "er": data.get("engagement_rate") or 0,
            "captured_at": datetime.utcnow().isoformat() + "Z",
        }
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ig_snapshots FROM communities WHERE id = %s", (community_id,))
                row = cur.fetchone()
                snapshots = list((row["ig_snapshots"] or []) if row else [])
                snapshots.append(snapshot)
                cur.execute("""
                    UPDATE communities
                    SET instagram_data = %s, ig_snapshots = %s, updated_at = NOW()
                    WHERE id = %s
                """, (psycopg2.extras.Json(data), psycopg2.extras.Json(snapshots), community_id))
            conn.commit()
        print(f"[pipeline] Completed for community {community_id}")
    except Exception as e:
        print(f"[pipeline] Error for community {community_id}: {e}")


def run_substack_pipeline(community_id, substack_url):
    try:
        import xml.etree.ElementTree as ET
        feed_url = substack_url.rstrip('/') + '/feed'
        resp = requests.get(feed_url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find('channel')
        posts = []
        for item in (channel.findall('item') if channel is not None else [])[:10]:
            enclosure = item.find('enclosure')
            media_content = item.find('{http://search.yahoo.com/mrss/}content')
            image_url = None
            if enclosure is not None and enclosure.get('type', '').startswith('image'):
                image_url = enclosure.get('url')
            elif media_content is not None:
                image_url = media_content.get('url')
            posts.append({
                'title': (item.findtext('title') or '').strip(),
                'link': (item.findtext('link') or '').strip(),
                'date': (item.findtext('pubDate') or '').strip(),
                'excerpt': (item.findtext('description') or '')[:200],
                'image_url': image_url,
            })
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE communities SET substack_data = %s, updated_at = NOW() WHERE id = %s",
                    (psycopg2.extras.Json({'posts': posts}), community_id)
                )
            conn.commit()
        print(f"[substack] Fetched {len(posts)} posts for {community_id}")
    except Exception as e:
        print(f"[substack] Error for {community_id}: {e}")


# ── Community API ──────────────────────────────────────────────────────────────

@app.route("/api/community", methods=["POST"])
def create_community():
    data = request.json or {}
    community_id = str(uuid.uuid4())
    pw = data.get("password", "")
    pw_hash = hash_password(pw) if pw else None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO communities
                    (id, name, tagline, location, description, tags, active_members, website, cover_option, leader_name, email, capabilities, partnership_preferences, password_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                community_id,
                data.get("name"),
                data.get("tagline"),
                data.get("location"),
                data.get("description"),
                data.get("tags", []),
                data.get("active_members") or None,
                data.get("website"),
                data.get("cover_option", 1),
                data.get("leader_name"),
                data.get("email"),
                data.get("capabilities", []),
                data.get("partnership_preferences"),
                pw_hash,
            ))
        conn.commit()
    token = create_token({"id": community_id, "role": "community", "name": data.get("name", "")})
    return jsonify({"id": community_id, "token": token, "role": "community",
                    "user": {"id": community_id, "name": data.get("name", ""), "org": data.get("name", ""), "role": "community"}})


@app.route("/api/community/<community_id>", methods=["GET"])
def get_community(community_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


@app.route("/api/community/<community_id>", methods=["PUT"])
def update_community(community_id):
    data = request.json or {}
    allowed = ["name", "tagline", "location", "description", "tags",
               "active_members", "website", "cover_option", "substack_url",
               "leader_name", "email", "partnership_preferences", "capabilities",
               "archetype", "archetype_source", "archetype_reasoning", "archetype_confidence"]
    fields, values = [], []
    for field in allowed:
        if field in data:
            fields.append(f"{field} = %s")
            values.append(data[field] if data[field] != "" else None)
    if not fields:
        return jsonify({"error": "Nothing to update"}), 400
    values.append(community_id)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE communities SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s",
                values
            )
        conn.commit()
    if data.get("substack_url"):
        thread = threading.Thread(
            target=run_substack_pipeline,
            args=(community_id, data["substack_url"]),
            daemon=True,
        )
        thread.start()
    return jsonify({"ok": True})


# ── Supabase Storage ──────────────────────────────────────────────────────────

def upload_to_supabase(file_bytes, path, content_type):
    url = f"{SUPABASE_URL}/storage/v1/object/{STORAGE_BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type,
    }
    resp = requests.post(url, data=file_bytes, headers=headers, timeout=30)
    resp.raise_for_status()
    return f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{path}"


@app.route("/api/community/<community_id>/cover", methods=["POST"])
def upload_cover(community_id):
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"covers/{community_id}/cover.{ext}"
    url = upload_to_supabase(file.read(), path, file.content_type or "image/jpeg")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE communities SET cover_image_url = %s, updated_at = NOW() WHERE id = %s",
                (url, community_id),
            )
        conn.commit()
    return jsonify({"url": url})


@app.route("/api/community/<community_id>/media", methods=["POST"])
def upload_media(community_id):
    file = request.files.get("file")
    caption = request.form.get("caption", "")
    if not file:
        return jsonify({"error": "No file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"media/{community_id}/{int(time.time())}.{ext}"
    url = upload_to_supabase(file.read(), path, file.content_type or "image/jpeg")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE communities
                   SET media_items = COALESCE(media_items, '[]'::jsonb) || %s::jsonb,
                       updated_at = NOW()
                   WHERE id = %s""",
                (psycopg2.extras.Json([{"url": url, "caption": caption}]), community_id),
            )
        conn.commit()
    return jsonify({"url": url, "caption": caption})


@app.route("/api/community/<community_id>/case-study", methods=["POST"])
def add_case_study(community_id):
    images = []
    if request.content_type and "multipart" in request.content_type:
        brand = request.form.get("brand", "")
        year = request.form.get("year", "")
        description = request.form.get("description", "")
        files = request.files.getlist("files")
        for i, file in enumerate(files):
            if file and file.filename:
                ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
                path = f"case-studies/{community_id}/{int(time.time())}_{i}.{ext}"
                url = upload_to_supabase(file.read(), path, file.content_type or "image/jpeg")
                images.append(url)
    else:
        data = request.json or {}
        brand = data.get("brand", "")
        year = data.get("year", "")
        description = data.get("description", "")
    entry = {"brand": brand, "year": year, "description": description, "images": images, "verified": False}
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE communities
                   SET case_studies = COALESCE(case_studies, '[]'::jsonb) || %s::jsonb,
                       updated_at = NOW()
                   WHERE id = %s""",
                (psycopg2.extras.Json([entry]), community_id),
            )
        conn.commit()
    return jsonify({"ok": True, "entry": entry})


@app.route("/api/community/<community_id>/notable-member/<int:idx>/verify", methods=["PUT"])
def verify_notable_member(community_id, idx):
    verified = (request.json or {}).get("verified", True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT notable_members, active_members FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            members = list(row["notable_members"] or [])
            if idx >= len(members):
                return jsonify({"error": "Index out of range"}), 400
            members[idx]["verified"] = verified
            nm = calculate_nm(members, row["active_members"])
            cur.execute(
                "UPDATE communities SET notable_members = %s, network_multiplier = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(members), nm, community_id),
            )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/community/<community_id>/case-study/<int:idx>/verify", methods=["PUT"])
def verify_case_study(community_id, idx):
    verified = (request.json or {}).get("verified", True)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT case_studies FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            studies = list(row["case_studies"] or [])
            if idx >= len(studies):
                return jsonify({"error": "Index out of range"}), 400
            studies[idx]["verified"] = verified
            cur.execute(
                "UPDATE communities SET case_studies = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(studies), community_id),
            )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/community/<community_id>/suggest-archetype", methods=["POST"])
def suggest_archetype(community_id):
    import json as _json
    import anthropic

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    c = dict(row)
    ig = c.get("instagram_data") or {}
    ig_profile = ig.get("profile") or {}
    media = ig.get("media") or []
    # Recalculate ER using industry standard formula (not stored value)
    _followers = ig_profile.get("followers_count") or 0
    if media and _followers:
        _total = sum(p.get("like_count", 0) + p.get("comments_count", 0) for p in media)
        ig_er = round(_total / len(media) / _followers * 100, 2)
    else:
        ig_er = None

    captions = []
    for post in media[:12]:
        cap = (post.get("caption") or "").strip()
        if cap:
            captions.append(f"- {cap[:200]}")

    members = c.get("notable_members") or []
    member_lines = [
        f"- {m.get('name','')} | role: {m.get('role','unspecified')} | @{m.get('ig_handle','')}"
        for m in members if m.get("name")
    ]

    prompt = f"""You are classifying a community for the Mayo partnership platform.

ARCHETYPES:
- evangelists: Brand awareness, cultural association. Members champion brands they genuinely believe in. Key signals: high share rate, unsolicited brand mentions, identity-linked content, tribal language.
- early_adopters: Product launches, first-mover campaigns. Members love being first. Key signals: trend-forward content, new product excitement, "first look" framing, innovation language.
- loyalists: Long-term sponsorship, repeat events. Members show up every time. Key signals: recurring event attendance, high retention language, community pride, consistency-focused content.
- buyers: Direct response, product seeding. Members convert. Key signals: purchase intent, reviews and recommendations, practical/functional content, "worth it" framing.

COMMUNITY DATA:

Name: {c.get('name') or '—'}
Tagline: {c.get('tagline') or '—'}
Description: {c.get('description') or '—'}
Location: {c.get('location') or '—'}
Interest tags: {', '.join(c.get('tags') or []) or '—'}
Active members: {c.get('active_members') or '—'}
Capabilities: {', '.join(c.get('capabilities') or []) or '—'}
Partnership preferences: {c.get('partnership_preferences') or '—'}

Instagram handle: @{ig_profile.get('username') or '—'}
Instagram followers: {ig_profile.get('followers_count') or '—'}
Instagram bio: {ig_profile.get('biography') or '—'}
Engagement rate: {f'{ig_er}%' if ig_er is not None else '—'} (industry standard: avg likes+comments / followers)

Recent captions:
{chr(10).join(captions) if captions else '— none available —'}

Notable members:
{chr(10).join(member_lines) if member_lines else '— none listed —'}

TASK:
Based on these signals, determine which single archetype best fits this community.
Go beyond the surface label — consider what communities built around these interest areas typically care about, how they relate to brands, and what the language and content patterns reveal about member motivation.

Respond with JSON only. No preamble, no markdown, no explanation outside the JSON:
{{"archetype":"evangelists|early_adopters|loyalists|buyers","confidence":0-100,"reasoning":"2-3 sentences citing the specific signals that drove this recommendation"}}"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        result = parse_claude_json(message.content[0].text)
        # Validate archetype value
        valid = {"evangelists", "early_adopters", "loyalists", "buyers"}
        if result.get("archetype") not in valid:
            return jsonify({"error": "Invalid archetype returned"}), 500
        return jsonify(result)
    except _json.JSONDecodeError:
        return jsonify({"error": "Could not parse AI response"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/community/<community_id>/notable-member", methods=["POST"])
def add_notable_member(community_id):
    data = request.json or {}
    entry = {
        "name": data.get("name", ""),
        "ig_handle": data.get("ig_handle", "").lstrip("@"),
        "role": data.get("role", ""),
        "verified": False,
    }
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE communities
                   SET notable_members = COALESCE(notable_members, '[]'::jsonb) || %s::jsonb,
                       updated_at = NOW()
                   WHERE id = %s""",
                (psycopg2.extras.Json([entry]), community_id),
            )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/community/<community_id>/notable-member/<int:idx>/tier", methods=["PUT"])
def set_member_tier(community_id, idx):
    tier = (request.json or {}).get("follower_tier")
    if tier not in ("micro", "mid", "macro", None):
        return jsonify({"error": "Invalid tier"}), 400
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT notable_members, active_members FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            members = list(row["notable_members"] or [])
            if idx >= len(members):
                return jsonify({"error": "Index out of range"}), 400
            if tier:
                members[idx]["follower_tier"] = tier
            else:
                members[idx].pop("follower_tier", None)
            nm = calculate_nm(members, row["active_members"])
            cur.execute(
                "UPDATE communities SET notable_members = %s, network_multiplier = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(members), nm, community_id),
            )
        conn.commit()
    return jsonify({"ok": True, "network_multiplier": nm})


@app.route("/api/community/<community_id>/notable-member/<int:idx>/followers", methods=["PUT"])
def set_member_followers(community_id, idx):
    """Save actual follower count (and optional ER) for a verified member. Recalculates NM."""
    data = request.json or {}
    ig_followers = data.get("ig_followers")
    ig_er = data.get("ig_er")
    if ig_followers is not None:
        try:
            ig_followers = int(ig_followers)
        except (ValueError, TypeError):
            return jsonify({"error": "ig_followers must be an integer"}), 400
    if ig_er is not None:
        try:
            ig_er = float(ig_er)
        except (ValueError, TypeError):
            return jsonify({"error": "ig_er must be a number"}), 400
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT notable_members, active_members FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            members = list(row["notable_members"] or [])
            if idx >= len(members):
                return jsonify({"error": "Index out of range"}), 400
            if ig_followers is not None:
                members[idx]["ig_followers"] = ig_followers
            else:
                members[idx].pop("ig_followers", None)
            if ig_er is not None:
                members[idx]["ig_er"] = ig_er
            else:
                members[idx].pop("ig_er", None)
            nm = calculate_nm(members, row["active_members"])
            cur.execute(
                "UPDATE communities SET notable_members = %s, network_multiplier = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(members), nm, community_id),
            )
        conn.commit()
    return jsonify({"ok": True, "network_multiplier": nm})


@app.route("/api/community/<community_id>/fetch-press", methods=["POST"])
def fetch_press(community_id):
    import xml.etree.ElementTree as ET
    import urllib.parse
    import json as _json
    import anthropic

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, location, description, tags, instagram_data, press_mentions FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    c = dict(row)
    ig_handle = ((c.get("instagram_data") or {}).get("profile") or {}).get("username") or ""
    query_parts = [c["name"]]
    if c.get("location"):
        query_parts.append(c["location"])
    query = " ".join(query_parts)

    feed_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        resp = requests.get(feed_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        items = []
        for item in (channel.findall("item") if channel is not None else [])[:15]:
            source_el = item.find("source")
            items.append({
                "title":   (item.findtext("title") or "").strip(),
                "url":     (item.findtext("link") or "").strip(),
                "date":    (item.findtext("pubDate") or "").strip(),
                "outlet":  source_el.text.strip() if source_el is not None else "Unknown",
                "snippet": (item.findtext("description") or "")[:300].strip(),
            })
    except Exception as e:
        return jsonify({"error": f"News fetch failed: {e}"}), 500

    if not items:
        return jsonify({"added": 0, "mentions": []})

    existing_urls = {m.get("url") for m in (c.get("press_mentions") or [])}
    new_items = [i for i in items if i["url"] not in existing_urls]
    if not new_items:
        return jsonify({"added": 0, "mentions": []})

    articles_text = "\n\n".join(
        f"[{i+1}] Title: {item['title']}\nOutlet: {item['outlet']}\nDate: {item['date']}\nSnippet: {item['snippet']}"
        for i, item in enumerate(new_items)
    )

    prompt = f"""You are evaluating news articles to identify genuine editorial press coverage of a specific community.

COMMUNITY:
Name: {c['name']}
Location: {c.get('location') or '—'}
Description: {(c.get('description') or '')[:300]}
Instagram: @{ig_handle}
Tags: {', '.join(c.get('tags') or [])}

ARTICLES:
{articles_text}

For each article evaluate:
1. Is it genuinely about THIS specific community — not a coincidental name match or unrelated entity?
2. Is it editorial (unsolicited)? Exclude press releases, paid placements, and content the community authored itself.
3. Type: feature = community is primary subject | list = roundup/listicle including the community | mention = referenced in passing
4. Outlet tier: national = major national publication | regional = city/regional media | niche = topic-specific publication | unknown

Respond with a JSON array, one entry per article in the same order. No preamble:
[{{"relevant":true/false,"editorial":true/false,"type":"feature|list|mention","outlet_tier":"national|regional|niche|unknown","reason":"one sentence"}}]"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        evaluations = parse_claude_json(message.content[0].text)
    except Exception as e:
        return jsonify({"error": f"AI evaluation failed: {e}"}), 500

    new_mentions = []
    for item, ev in zip(new_items, evaluations):
        if not ev.get("relevant") or not ev.get("editorial"):
            continue
        new_mentions.append({
            **item,
            "type":        ev.get("type", "mention"),
            "outlet_tier": ev.get("outlet_tier", "unknown"),
            "ai_reason":   ev.get("reason", ""),
            "confirmed":   None,  # pending admin review
        })

    if new_mentions:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT press_mentions FROM communities WHERE id = %s", (community_id,))
                existing = list((cur.fetchone()["press_mentions"] or []))
                cur.execute(
                    "UPDATE communities SET press_mentions = %s, updated_at = NOW() WHERE id = %s",
                    (psycopg2.extras.Json(existing + new_mentions), community_id),
                )
            conn.commit()

    return jsonify({"added": len(new_mentions), "mentions": new_mentions})


@app.route("/api/community/<community_id>/press-mention/<int:idx>/confirm", methods=["PUT"])
def confirm_press_mention(community_id, idx):
    confirmed = (request.json or {}).get("confirmed")  # True, False, or None (reset to pending)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT press_mentions, case_studies, miq_score, ig_snapshots FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            mentions = list(row["press_mentions"] or [])
            if idx >= len(mentions):
                return jsonify({"error": "Index out of range"}), 400
            mentions[idx]["confirmed"] = confirmed
            pmm = calculate_pmm(mentions)
            bah = calculate_bah(row["case_studies"] or [])
            gv  = calculate_gv(row["ig_snapshots"] or [])
            cis_raw = calculate_cis_raw(row.get("miq_score"), gv, bah, pmm)
            cur.execute(
                "UPDATE communities SET press_mentions = %s, cis_raw = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(mentions), cis_raw, community_id),
            )
        conn.commit()
    return jsonify({"ok": True, "cis_raw": cis_raw})


@app.route("/api/community/<community_id>/analyse-miq", methods=["POST"])
def analyse_miq(community_id):
    import json as _json
    import anthropic

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, description, tags, notable_members, case_studies, ig_snapshots, press_mentions FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404

    c = dict(row)
    verified_members = [m for m in (c.get("notable_members") or []) if m.get("verified")]
    if not verified_members:
        return jsonify({"error": "No verified members to analyse"}), 400

    member_lines = "\n".join(
        f"- {m.get('name','—')} | Role: {m.get('role') or 'unspecified'} | @{m.get('ig_handle','')}"
        for m in verified_members
    )

    prompt = f"""You are scoring the Member Influence Quality (MIQ) for a community on the Mayo brand partnership platform.

MIQ measures the cultural credibility and brand-relevance of the people in this community — not follower count, but WHO they are. A community of 50 professional athletes or senior journalists scores higher than 500 general consumers.

COMMUNITY:
Name: {c['name']}
Description: {(c.get('description') or '')[:300]}
Tags: {', '.join(c.get('tags') or [])}

VERIFIED NOTABLE MEMBERS:
{member_lines}

SCORING RUBRIC (0-100):
80-100: Significant cultural positions — pro athletes, established journalists, senior designers, recognised artists, industry executives
60-79: Clear professional identity in relevant fields — coaches, niche-authority creators, rising professionals
40-59: Some professional context but roles are generic or unclear
20-39: Active community participants without notable professional distinction
0-19: Insufficient information

Respond with JSON only. No preamble:
{{"miq_score":0-100,"reasoning":"2-3 sentences citing specific roles and their cultural relevance to brand partnerships"}}"""

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        result = parse_claude_json(message.content[0].text)
        miq_score    = int(result["miq_score"])
        miq_reasoning = result.get("reasoning", "")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    with get_db() as conn:
        with conn.cursor() as cur:
            gv  = calculate_gv(c.get("ig_snapshots") or [])
            bah = calculate_bah(c.get("case_studies") or [])
            pmm = calculate_pmm(c.get("press_mentions") or [])
            cis_raw = calculate_cis_raw(miq_score, gv, bah, pmm)
            cur.execute(
                "UPDATE communities SET miq_score = %s, miq_reasoning = %s, cis_raw = %s, updated_at = NOW() WHERE id = %s",
                (miq_score, miq_reasoning, cis_raw, community_id),
            )
        conn.commit()

    return jsonify({"miq_score": miq_score, "reasoning": miq_reasoning, "cis_raw": cis_raw})


@app.route("/api/community/<community_id>/apply-cis-stamp", methods=["POST"])
def apply_cis_stamp(community_id):
    data = request.json or {}
    stamped_score = data.get("stamped_score")
    stamped_by    = data.get("stamped_by", "admin")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cis_raw FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            cis_raw = row["cis_raw"]
            if stamped_score is None:
                cur.execute(
                    "UPDATE communities SET cis_stamped = NULL, cis_stamp_by = NULL, cis_stamped_at = NULL, cis_stamp_expires_at = NULL, updated_at = NOW() WHERE id = %s",
                    (community_id,),
                )
            else:
                stamped_score = int(stamped_score)
                if cis_raw is None:
                    return jsonify({"error": "No raw CIS to stamp yet"}), 400
                if abs(stamped_score - cis_raw) > 15:
                    return jsonify({"error": f"Stamp must be within ±15 of raw score ({cis_raw})"}), 400
                cur.execute(
                    """UPDATE communities
                       SET cis_stamped = %s, cis_stamp_by = %s,
                           cis_stamped_at = NOW(),
                           cis_stamp_expires_at = NOW() + INTERVAL '90 days',
                           updated_at = NOW()
                       WHERE id = %s""",
                    (stamped_score, stamped_by, community_id),
                )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/community/<community_id>/recalculate", methods=["POST"])
def recalculate_metrics(community_id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            c = dict(row)
            nm  = calculate_nm(c.get("notable_members"), c.get("active_members"))
            gv  = calculate_gv(c.get("ig_snapshots") or [])
            bah = calculate_bah(c.get("case_studies") or [])
            pmm = calculate_pmm(c.get("press_mentions") or [])
            cis_raw = calculate_cis_raw(c.get("miq_score"), gv, bah, pmm)
            cur.execute(
                "UPDATE communities SET network_multiplier = %s, cis_raw = %s, updated_at = NOW() WHERE id = %s",
                (nm, cis_raw, community_id),
            )
        conn.commit()
    return jsonify({"network_multiplier": nm, "cis_raw": cis_raw, "gv": gv, "bah": bah, "pmm": pmm, "miq": c.get("miq_score")})


@app.route("/api/community/<community_id>/refresh-instagram", methods=["POST"])
def refresh_instagram(community_id):
    """Re-run Instagram and Substack pipelines using stored credentials."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT instagram_token, substack_url FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
    if not row:
        return jsonify({"error": "Community not found."}), 404
    started = []
    if row["instagram_token"]:
        threading.Thread(target=run_instagram_pipeline, args=(community_id, row["instagram_token"]), daemon=True).start()
        started.append("Instagram")
    if row["substack_url"]:
        threading.Thread(target=run_substack_pipeline, args=(community_id, row["substack_url"]), daemon=True).start()
        started.append("Substack")
    if not started:
        return jsonify({"error": "No connected channels found. Connect Instagram or Substack first."}), 400
    return jsonify({"ok": True, "message": f"{' & '.join(started)} sync started. Refresh in a few seconds."})


# ── Instagram OAuth ────────────────────────────────────────────────────────────

@app.route("/login")
def login():
    community_id = request.args.get("community_id", "")
    auth_url = (
        "https://www.instagram.com/oauth/authorize"
        f"?client_id={META_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=instagram_business_basic,instagram_business_manage_insights"
        "&response_type=code"
        f"&state={community_id}"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback():
    code = request.args.get("code", "").split("#")[0]
    community_id = request.args.get("state", "")

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
    if not token_response.ok:
        return f"Token exchange failed: {token_response.status_code} — {token_response.text}", 500

    token_data = token_response.json()
    short_lived_token = token_data["access_token"]
    instagram_user_id = str(token_data.get("user_id", ""))

    # Upgrade to long-lived token (60 days)
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

    # Save token to DB
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE communities
                SET instagram_token = %s,
                    instagram_user_id = %s,
                    instagram_connected_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (long_lived_token, instagram_user_id, community_id))
        conn.commit()

    # Run pipeline in background
    thread = threading.Thread(
        target=run_instagram_pipeline,
        args=(community_id, long_lived_token),
        daemon=True,
    )
    thread.start()

    return redirect(f"/onboard?community_id={community_id}&instagram_connected=true&step=3")


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    with get_db() as conn:
        with conn.cursor() as cur:
            # Check brands first
            cur.execute("SELECT * FROM brands WHERE LOWER(email) = %s", (email,))
            brand = cur.fetchone()
            if brand:
                brand = dict(brand)
                if not verify_password(password, brand.get("password_hash", "")):
                    return jsonify({"error": "Invalid credentials"}), 401
                token = create_token({"id": brand["id"], "role": "brand", "name": brand["name"]})
                return jsonify({"token": token, "role": "brand",
                                "user": {"id": brand["id"], "name": brand["name"], "org": brand["name"],
                                         "role": "brand", "initial": (brand.get("initial") or brand["name"][0]).upper()}})
            # Check communities
            cur.execute("SELECT id, name, leader_name, email, password_hash FROM communities WHERE LOWER(email) = %s", (email,))
            community = cur.fetchone()
            if not community:
                return jsonify({"error": "No account found with that email"}), 404
            community = dict(community)
            if not community.get("password_hash"):
                return jsonify({"error": "No password set — use your setup link to create one"}), 401
            if not verify_password(password, community["password_hash"]):
                return jsonify({"error": "Invalid credentials"}), 401
            leader = community.get("leader_name") or community["name"]
            token = create_token({"id": community["id"], "role": "community", "name": community["name"]})
            return jsonify({"token": token, "role": "community",
                            "user": {"id": community["id"], "name": community["name"], "leader_name": leader,
                                     "org": community["name"], "role": "community",
                                     "initial": (leader or "C")[0].upper()}})


def _extract_domain(url):
    """Return bare domain (no www) from a URL or domain string."""
    import urllib.parse
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        return urllib.parse.urlparse(url).hostname.lstrip("www.").lower()
    except Exception:
        return ""


@app.route("/api/register/brand", methods=["POST"])
def register_brand():
    data = request.json or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()
    website = (data.get("website") or "").strip()
    if not email or not password or not name:
        return jsonify({"error": "Name, email and password required"}), 400

    # Domain validation — email must share domain with brand website
    if website:
        email_domain = email.split("@")[-1] if "@" in email else ""
        site_domain = _extract_domain(website)
        if email_domain and site_domain:
            if email_domain != site_domain and not email_domain.endswith("." + site_domain) and not site_domain.endswith("." + email_domain):
                return jsonify({
                    "error": f"Email domain ({email_domain}) must match your website domain ({site_domain}). Use a brand email address."
                }), 400

    brand_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    initial = name[0].upper()
    social_links = data.get("social_links") or {}
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO brands (id, name, email, password_hash, tagline, bio, website, category,
                                        color, gradient, initial, verified, leader_name, leader_role,
                                        values, looking_for, social_links)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (brand_id, name, email, pw_hash,
                      data.get("tagline"), data.get("bio"), website,
                      data.get("industry") or data.get("category"), data.get("color", "#888"),
                      data.get("gradient"), initial, False,
                      data.get("leader_name"), data.get("leader_role"),
                      data.get("values"), data.get("looking_for"),
                      _json_stdlib.dumps(social_links)))
            conn.commit()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "An account with that email already exists"}), 409
    token = create_token({"id": brand_id, "role": "brand", "name": name})
    return jsonify({"token": token, "role": "brand",
                    "user": {"id": brand_id, "name": name, "org": name, "role": "brand", "initial": initial}})


# ── Public community listing ───────────────────────────────────────────────────

@app.route("/api/communities", methods=["GET"])
def list_communities():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, tagline, location, description, tags, active_members, website,
                       cover_option, cover_image_url, archetype, archetype_source, archetype_reasoning,
                       network_multiplier, cis_raw, cis_stamped, instagram_data, instagram_token,
                       notable_members, case_studies, capabilities, partnership_preferences,
                       leader_name, email, substack_url, substack_data,
                       miq_score, miq_reasoning, press_mentions, media_items, created_at
                FROM communities ORDER BY created_at DESC
            """)
            rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return jsonify(result)


# ── Briefs ────────────────────────────────────────────────────────────────────

@app.route("/api/briefs", methods=["GET"])
def list_briefs():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT br.*, b.name AS brand_name, b.tagline AS brand_tagline,
                       b.bio AS brand_bio, b.color AS brand_color, b.gradient AS brand_gradient, b.initial AS brand_initial
                FROM briefs br
                LEFT JOIN brands b ON br.brand_id = b.id
                WHERE br.status = 'open'
                ORDER BY br.created_at DESC
            """)
            rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return jsonify(result)


@app.route("/api/briefs", methods=["POST"])
def create_brief():
    payload = require_auth(request)
    if not payload or payload.get("role") != "brand":
        return jsonify({"error": "Brand login required"}), 401
    data = request.json or {}
    brief_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO briefs (id, brand_id, title, campaign_goal, partnership_type, budget, budget_period,
                    tags, requirements, kpis, products, deliverables, deadline, activation_window, goal, looking_for)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                brief_id, payload["id"],
                data.get("title"), data.get("campaign_goal"), data.get("partnership_type"),
                data.get("budget"), data.get("budget_period"),
                data.get("tags", []),
                psycopg2.extras.Json(data.get("requirements", {})),
                psycopg2.extras.Json(data.get("kpis", [])),
                psycopg2.extras.Json(data.get("products", [])),
                psycopg2.extras.Json(data.get("deliverables", [])),
                data.get("deadline"), data.get("activation_window"),
                data.get("goal"), data.get("looking_for"),
            ))
            # Fetch the brand info to return with the brief
            cur.execute("""
                SELECT br.*, b.name AS brand_name, b.tagline AS brand_tagline,
                       b.bio AS brand_bio, b.color AS brand_color, b.gradient AS brand_gradient, b.initial AS brand_initial
                FROM briefs br LEFT JOIN brands b ON br.brand_id = b.id WHERE br.id = %s
            """, (brief_id,))
            row = cur.fetchone()
        conn.commit()
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
    return jsonify(d), 201


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect("/app")


@app.route("/app")
def app_shell():
    return render_template("app.html")


@app.route("/onboard")
def onboard():
    return render_template("onboarding.html")


@app.route("/onboard/brand")
def onboard_brand():
    return render_template("brand_onboarding.html")


@app.route("/admin")
def admin():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return "Unauthorized", 403
    return render_template("admin.html", admin_token=ADMIN_TOKEN)


@app.route("/api/admin/communities")
def admin_communities():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM communities ORDER BY created_at DESC")
            rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        # Convert datetime objects to strings
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return jsonify(result)


@app.route("/api/admin/briefs")
def admin_briefs():
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT br.*, b.name AS brand_name, b.color AS brand_color
                FROM briefs br
                LEFT JOIN brands b ON br.brand_id = b.id
                ORDER BY br.created_at DESC
            """)
            rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        result.append(d)
    return jsonify(result)


@app.route("/api/briefs/<brief_id>/cover", methods=["POST"])
def upload_brief_cover(brief_id):
    """Upload a cover image for a brief. Accepts multipart form with 'file' field."""
    import uuid as _uuid
    import base64 as _base64
    payload = require_auth(request)
    if not payload:
        # Also allow admin token
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token != ADMIN_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        return jsonify({"error": "Invalid file type"}), 400
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}.get(file.content_type, "jpg")
    path = f"briefs/{brief_id}/cover.{ext}"
    url = upload_to_supabase(file.read(), path, file.content_type)
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE briefs SET cover_image_url = %s WHERE id = %s", (url, brief_id))
        conn.commit()
    return jsonify({"ok": True, "url": url})


@app.route("/api/brand/<brand_id>/header", methods=["POST"])
def upload_brand_header(brand_id):
    auth = require_auth(request)
    if not auth or (auth.get("id") != brand_id and auth.get("role") != "admin"):
        return jsonify({"error": "Unauthorized"}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"brands/{brand_id}/header.{ext}"
    url = upload_to_supabase(file.read(), path, file.content_type or "image/jpeg")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE brands SET header_image_url = %s WHERE id = %s", (url, brand_id))
        conn.commit()
    return jsonify({"url": url})


@app.route("/api/brand/<brand_id>/profile-image", methods=["POST"])
def upload_brand_profile_image(brand_id):
    auth = require_auth(request)
    if not auth or (auth.get("id") != brand_id and auth.get("role") != "admin"):
        return jsonify({"error": "Unauthorized"}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    path = f"brands/{brand_id}/profile.{ext}"
    url = upload_to_supabase(file.read(), path, file.content_type or "image/jpeg")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE brands SET profile_image_url = %s WHERE id = %s", (url, brand_id))
        conn.commit()
    return jsonify({"url": url})


@app.route("/api/brand/<brand_id>", methods=["GET"])
def get_brand_profile(brand_id):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Ensure past_partnerships column exists
                cur.execute("ALTER TABLE brands ADD COLUMN IF NOT EXISTS past_partnerships JSONB DEFAULT '[]'")
                conn.commit()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name, tagline, bio, website, category, color, initial,
                           leader_name, leader_role, "values", looking_for, social_links,
                           profile_image_url, header_image_url, past_partnerships,
                           verified, created_at
                    FROM brands WHERE id = %s
                """, (brand_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"error": "Not found"}), 404
                # RealDictCursor already returns a dict — no zip needed
                brand = dict(row)
                brand["past_partnerships"] = brand["past_partnerships"] or []
                brand["social_links"] = brand["social_links"] or {}
                if brand["created_at"]:
                    brand["created_at"] = brand["created_at"].isoformat()
                # Attach briefs
                cur.execute("""
                    SELECT id, title, partnership_type, budget, budget_period, status,
                           tags, cover_image_url, response_count
                    FROM briefs WHERE brand_id = %s ORDER BY created_at DESC
                """, (brand_id,))
                brand["briefs"] = [dict(r) for r in cur.fetchall()]
        return jsonify(brand)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/brand/<brand_id>/past-partnerships", methods=["PUT"])
def update_past_partnerships(brand_id):
    auth = require_auth(request)
    if not auth or (auth.get("id") != brand_id and auth.get("role") != "admin"):
        return jsonify({"error": "Unauthorized"}), 403
    data = request.json or {}
    partnerships = data.get("past_partnerships", [])
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE brands SET past_partnerships = %s WHERE id = %s",
                (_json_stdlib.dumps(partnerships), brand_id)
            )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/briefs/<brief_id>", methods=["DELETE"])
def admin_delete_brief(brief_id):
    token = request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return jsonify({"error": "Unauthorized"}), 403
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM briefs WHERE id = %s", (brief_id,))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/profile/<community_id>")
def public_profile(community_id):
    return render_template("profile.html", community_id=community_id)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
