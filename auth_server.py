"""
Mayo — Flask app
Serves the community onboarding flow, handles Instagram OAuth,
stores community profiles in PostgreSQL, and runs the data pipeline.
"""

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
STORAGE_BUCKET = "mayo-assets"

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
            ]:
                cur.execute(f"""
                    ALTER TABLE communities ADD COLUMN IF NOT EXISTS {col} {typedef}
                """)
        conn.commit()


try:
    init_db()
except Exception as e:
    print(f"[db] Could not initialise database: {e}")


# ── Background pipeline ────────────────────────────────────────────────────────

def run_instagram_pipeline(community_id, token):
    try:
        import connectors.instagram as ig
        ig.ACCESS_TOKEN = token
        data = ig.collect()
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE communities
                    SET instagram_data = %s, updated_at = NOW()
                    WHERE id = %s
                """, (psycopg2.extras.Json(data), community_id))
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
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO communities
                    (id, name, tagline, location, description, tags, active_members, website, cover_option, leader_name, email, capabilities, partnership_preferences)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            ))
        conn.commit()
    return jsonify({"id": community_id})


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
               "archetype", "archetype_source"]
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
            cur.execute("SELECT notable_members FROM communities WHERE id = %s", (community_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            members = list(row["notable_members"] or [])
            if idx >= len(members):
                return jsonify({"error": "Index out of range"}), 400
            members[idx]["verified"] = verified
            cur.execute(
                "UPDATE communities SET notable_members = %s, updated_at = NOW() WHERE id = %s",
                (psycopg2.extras.Json(members), community_id),
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

    return redirect(f"/?community_id={community_id}&instagram_connected=true&step=3")


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("onboarding.html")


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


@app.route("/profile/<community_id>")
def public_profile(community_id):
    return render_template("profile.html", community_id=community_id)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
