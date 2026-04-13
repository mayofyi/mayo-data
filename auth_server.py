"""
Mayo — Flask app
Serves the community onboarding flow, handles Instagram OAuth,
stores community profiles in PostgreSQL, and runs the data pipeline.
"""

import os
import threading
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

# Render uses postgres:// but psycopg2 requires postgresql://
_db_url = os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1)
DATABASE_URL = _db_url if "sslmode" in _db_url else _db_url + "?sslmode=require"

app = Flask(__name__)


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
                    substack_url TEXT,
                    instagram_token TEXT,
                    instagram_user_id TEXT,
                    instagram_data JSONB,
                    instagram_connected_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
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


# ── Community API ──────────────────────────────────────────────────────────────

@app.route("/api/community", methods=["POST"])
def create_community():
    data = request.json or {}
    community_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO communities
                    (id, name, tagline, location, description, tags, active_members, website, cover_option)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
               "active_members", "website", "cover_option", "substack_url"]
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
