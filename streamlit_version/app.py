# ╔══════════════════════════════════════════════════════════════════════════╗
# ║   AI TRAVEL ITINERARY PLANNER — PREMIUM UI v4.0  (MySQL Edition)       ║
# ║   pip install streamlit openai reportlab plotly requests                ║
# ║               mysql-connector-python                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝

import streamlit as st
import hashlib, os, uuid, smtplib, re, base64
from datetime import date, datetime
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import mysql.connector
import plotly.graph_objects as go
import plotly.express as px
import requests
from openai import OpenAI

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  — replace with env vars before sharing
# ════════════════════════════════════════════════════════════════════════════
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY",  "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
SMTP_HOST       = os.getenv("SMTP_HOST",  "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER_ADDR  = os.getenv("SMTP_USER",  "")
SMTP_PASS       = os.getenv("SMTP_PASS",  "")

# MySQL — edit these or set environment variables to match your phpMyAdmin setup
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "travel_planner")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")

CURRENCY_SYMBOLS = {
    "USD":"$","EUR":"€","GBP":"£","AUD":"A$","CAD":"C$",
    "JPY":"¥","AED":"د.إ","SGD":"S$","INR":"₹","MYR":"RM","LKR":"Rs "
}
CURRENCY_LIST = ["USD","EUR","GBP","AUD","CAD","JPY","AED","SGD","INR","MYR","LKR"]
def csym(code): return CURRENCY_SYMBOLS.get(code, code+" ")

# ════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ════════════════════════════════════════════════════════════════════════════
def _make_conn(db=DB_NAME):
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, database=db or None,
        user=DB_USER, password=DB_PASS,
        autocommit=True, charset="utf8mb4", connection_timeout=10
    )

def get_db():
    return _make_conn()

def init_db():
    conn = _make_conn(db=None); cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.close(); conn.close()

    conn = get_db(); cur = conn.cursor()

    # ── Regular users table ──────────────────────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        username      VARCHAR(100) NOT NULL PRIMARY KEY,
        password_hash VARCHAR(255) NOT NULL,
        full_name     VARCHAR(200) NOT NULL,
        email         VARCHAR(200) DEFAULT '',
        avatar        VARCHAR(10)  DEFAULT 'U',
        pref_currency VARCHAR(10)  DEFAULT 'USD',
        last_login    DATETIME     DEFAULT NULL,
        created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── Admins table (separate from users) ───────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS admins (
        username      VARCHAR(100) NOT NULL PRIMARY KEY,
        password_hash VARCHAR(255) NOT NULL,
        full_name     VARCHAR(200) NOT NULL,
        email         VARCHAR(200) DEFAULT '',
        last_login    DATETIME     DEFAULT NULL,
        created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # ── Itineraries (linked to users table) ──────────────────────────────────
    cur.execute("""CREATE TABLE IF NOT EXISTS itineraries (
        id               VARCHAR(36)   NOT NULL PRIMARY KEY,
        user             VARCHAR(100)  NOT NULL,
        destination      VARCHAR(300)  DEFAULT '',
        days             INT           DEFAULT 1,
        start_date       VARCHAR(20)   DEFAULT '',
        budget           DECIMAL(14,2) DEFAULT 0,
        travelers        INT           DEFAULT 1,
        travel_type      VARCHAR(100)  DEFAULT '',
        activities       TEXT,
        notes            TEXT,
        accommodation    VARCHAR(100)  DEFAULT 'Any',
        transport        VARCHAR(100)  DEFAULT 'Any',
        meal_pref        VARCHAR(100)  DEFAULT 'No preference',
        pace             VARCHAR(50)   DEFAULT 'Moderate',
        fitness          VARCHAR(100)  DEFAULT 'Moderate',
        must_visit       TEXT,
        avoid            TEXT,
        group_type       VARCHAR(100)  DEFAULT 'Solo',
        kids_ages        VARCHAR(200)  DEFAULT '',
        eco              TINYINT(1)    DEFAULT 0,
        pet              TINYINT(1)    DEFAULT 0,
        trip_theme       VARCHAR(100)  DEFAULT 'General',
        day_start        VARCHAR(50)   DEFAULT 'Standard (8 am)',
        restaurant_meals INT           DEFAULT 2,
        nightlife        TINYINT(1)    DEFAULT 0,
        off_peak         TINYINT(1)    DEFAULT 0,
        budget_priority  VARCHAR(100)  DEFAULT 'Balanced',
        currency         VARCHAR(10)   DEFAULT 'USD',
        itinerary        LONGTEXT,
        packing_list     LONGTEXT,
        saved_on         VARCHAR(20)   DEFAULT '',
        starred          TINYINT(1)    DEFAULT 0,
        created_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    cur.execute("""CREATE TABLE IF NOT EXISTS expenses (
        id           VARCHAR(36)   NOT NULL PRIMARY KEY,
        itinerary_id VARCHAR(36)   NOT NULL,
        user         VARCHAR(100)  NOT NULL,
        date         VARCHAR(20)   DEFAULT '',
        category     VARCHAR(100)  DEFAULT '',
        description  TEXT,
        amount       DECIMAL(12,2) DEFAULT 0,
        created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # Add email-verification columns (safe on existing DB — ignored if already present)
    for _col_sql in [
        "ALTER TABLE users ADD COLUMN verified       TINYINT(1)   NOT NULL DEFAULT 1",
        "ALTER TABLE users ADD COLUMN verify_token   VARCHAR(64)  DEFAULT NULL",
        "ALTER TABLE users ADD COLUMN profile_photo  MEDIUMBLOB   DEFAULT NULL",
    ]:
        try:
            cur.execute(_col_sql)
        except Exception:
            pass  # column already exists

    # Seed default user (pre-verified so demo account always works)
    cur.execute("SELECT 1 FROM users WHERE username='traveler'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username,password_hash,full_name,verified) VALUES (%s,%s,%s,1)",
            ("traveler", _hash_pw("Travel@123"), "Demo Traveler"))

    # Seed default admin
    cur.execute("SELECT 1 FROM admins WHERE username='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username,password_hash,full_name) VALUES (%s,%s,%s)",
                    ("admin", _hash_pw("Admin@1234"), "Administrator"))

    cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# PASSWORD HASHING  — PBKDF2-SHA256 (standard library, no extra package)
# ════════════════════════════════════════════════════════════════════════════
def _hash_pw(plain: str) -> str:
    salt = os.urandom(16).hex()
    dk   = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000).hex()
    return f"pbkdf2:{salt}:{dk}"

def _check_pw(plain: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split(":", 2)
        return hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000).hex() == dk
    except Exception:
        return False

def hash_pw(p): return _hash_pw(p)   # public alias used elsewhere

def pw_strength(p):
    score = sum([len(p)>=8, bool(re.search(r'[A-Z]',p)), bool(re.search(r'[a-z]',p)),
                 bool(re.search(r'\d',p)), bool(re.search(r'[^A-Za-z0-9]',p))])
    return ["Very Weak","Weak","Fair","Strong","Very Strong"][max(0,score-1)] if p else ""

# ════════════════════════════════════════════════════════════════════════════
# USER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
def authenticate_user(u, p):
    """Return (True, actual_username), ('unverified', None), or (False, None).
    Accepts either username or email in the `u` argument."""
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT username, password_hash, verified FROM users WHERE username=%s OR email=%s",
        (u, u)
    )
    row = cur.fetchone(); cur.close(); conn.close()
    if not row or not _check_pw(p, row["password_hash"]):
        return False, None
    if not row.get("verified", 1):
        return "unverified", None
    actual = row["username"]
    conn2 = get_db(); cur2 = conn2.cursor()
    cur2.execute("UPDATE users SET last_login=NOW() WHERE username=%s", (actual,))
    cur2.close(); conn2.close()
    return True, actual

def authenticate(u, p):
    return authenticate_user(u, p)

def register_user(u, p, n, email=""):
    errs = []
    if not u or len(u) < 3 or not re.match(r'^[a-zA-Z0-9_]+$', u):
        errs.append("Username must be 3+ characters (letters, numbers, underscore only).")
    if not n or len(n.strip()) < 1:
        errs.append("Full name is required.")
    if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email.strip()):
        errs.append("A valid email address is required.")
    if len(p) < 6:
        errs.append("Password must be at least 6 characters.")
    if not re.search(r'\d', p):
        errs.append("Password must contain at least one number.")
    if errs: return False, " ".join(errs)
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username=%s", (u,))
        if cur.fetchone():
            cur.close(); conn.close(); return False, "Username already taken. Choose another."
        cur.execute("SELECT 1 FROM users WHERE email=%s", (email.strip(),))
        if cur.fetchone():
            cur.close(); conn.close()
            return False, "Email already registered. Sign in with your existing account."
        token = os.urandom(32).hex()   # 64-char hex verification token
        cur.execute(
            "INSERT INTO users (username,password_hash,full_name,email,verified,verify_token) "
            "VALUES (%s,%s,%s,%s,0,%s)",
            (u, _hash_pw(p), n.strip(), email.strip(), token))
        conn.commit()
        cur.close(); conn.close()
        send_verification_email(email.strip(), n.strip(), token)
        return True, "Account created! Please check your email and click the verification link to activate your account."
    except Exception as e:
        return False, f"Registration failed: {e}"

def get_user_info(u):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username=%s", (u,))
    row = cur.fetchone()
    if row:
        cur.close(); conn.close()
        d = dict(row); d["name"] = d.get("full_name",""); d["role"] = "user"
        return d
    cur.execute("SELECT * FROM admins WHERE username=%s", (u,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row: return {}
    d = dict(row); d["name"] = d.get("full_name",""); d["role"] = "admin"
    return d

def load_users():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users ORDER BY created_at ASC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return {r["username"]: {
        "password": r["password_hash"], "role": "user",
        "name": r["full_name"], "email": r.get("email",""),
        "avatar": r.get("avatar","U"),
        "last_login": str(r["last_login"])[:16] if r.get("last_login") else "Never",
        "created_at": str(r["created_at"])[:10] if r.get("created_at") else "",
    } for r in rows}

def update_password(u, new_plain):
    h = _hash_pw(new_plain)
    conn = get_db(); cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash=%s WHERE username=%s", (h, u))
    if cur.rowcount == 0:
        cur.execute("UPDATE admins SET password_hash=%s WHERE username=%s", (h, u))
    cur.close(); conn.close()

def update_user_profile(u, full_name=None, email=None, avatar=None, pref_currency=None, profile_photo=None):
    sets, vals = [], []
    if full_name     is not None: sets.append("full_name=%s");      vals.append(full_name)
    if email         is not None: sets.append("email=%s");           vals.append(email)
    if avatar        is not None: sets.append("avatar=%s");          vals.append(avatar)
    if pref_currency is not None: sets.append("pref_currency=%s");   vals.append(pref_currency)
    if profile_photo is not None: sets.append("profile_photo=%s");   vals.append(profile_photo)
    if not sets: return
    vals.append(u)
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"UPDATE users SET {','.join(sets)} WHERE username=%s", vals)
    cur.close(); conn.close()

def get_profile_photo(u):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT profile_photo FROM users WHERE username=%s", (u,))
    row = cur.fetchone(); cur.close(); conn.close()
    return bytes(row[0]) if row and row[0] else None

def delete_user(u):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username=%s", (u,))
    cur.close(); conn.close()

# ── Admin-specific auth functions ────────────────────────────────────────────
def authenticate_admin(u, p):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT password_hash FROM admins WHERE username=%s", (u,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row or not _check_pw(p, row["password_hash"]): return False
    conn2 = get_db(); cur2 = conn2.cursor()
    cur2.execute("UPDATE admins SET last_login=NOW() WHERE username=%s", (u,))
    cur2.close(); conn2.close()
    return True

def register_admin(u, p, n, email=""):
    errs = []
    if len(u) < 3 or not re.match(r'^[a-zA-Z0-9_]+$', u):
        errs.append("Username: 3+ chars, letters/numbers/underscore only.")
    if len(p) < 8:
        errs.append("Password must be at least 8 characters.")
    if not re.search(r'[A-Z]', p):
        errs.append("Password must contain an uppercase letter.")
    if not re.search(r'\d', p):
        errs.append("Password must contain a number.")
    if not re.search(r'[^A-Za-z0-9]', p):
        errs.append("Password must contain a special character.")
    if errs: return False, " ".join(errs)
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT 1 FROM admins WHERE username=%s", (u,))
        if cur.fetchone():
            cur.close(); conn.close(); return False, "Admin username already taken."
        cur.execute(
            "INSERT INTO admins (username,password_hash,full_name,email) VALUES (%s,%s,%s,%s)",
            (u, _hash_pw(p), n.strip(), email.strip()))
        conn.commit()
        cur.close(); conn.close()
        return True, "Admin account created."
    except Exception as e:
        return False, f"Registration failed: {e}"

def load_admins():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM admins ORDER BY created_at ASC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return {r["username"]: {
        "name": r["full_name"], "email": r.get("email",""),
        "last_login": str(r["last_login"])[:16] if r.get("last_login") else "Never",
        "created_at": str(r["created_at"])[:10] if r.get("created_at") else "",
    } for r in rows}

def delete_admin(u):
    if u == "admin": return   # protect default admin
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE username=%s", (u,))
    cur.close(); conn.close()

# ════════════════════════════════════════════════════════════════════════════
# ITINERARY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
_ITIN_COLS = [
    "id","user","destination","days","start_date","budget","travelers",
    "travel_type","activities","notes","accommodation","transport",
    "meal_pref","pace","fitness","must_visit","avoid","group_type","kids_ages",
    "eco","pet","trip_theme","day_start","restaurant_meals","nightlife",
    "off_peak","budget_priority","currency","itinerary","packing_list",
    "saved_on","starred"]
_BOOL_COLS = {"eco","pet","nightlife","off_peak","starred"}

def _row_to_rec(row):
    rec = dict(row)
    for k in _BOOL_COLS: rec[k] = bool(rec.get(k, 0))
    if rec.get("budget") is not None: rec["budget"] = float(rec["budget"])
    for k in ("days","travelers","restaurant_meals"):
        if rec.get(k) is not None: rec[k] = int(rec[k])
    return rec

def save_itinerary(rec):
    conn = get_db(); cur = conn.cursor()
    cols = [c for c in _ITIN_COLS if c in rec]
    vals = [int(rec[c]) if c in _BOOL_COLS else rec.get(c) for c in cols]
    ph   = ",".join(["%s"]*len(cols))
    col_str = ",".join(f"`{c}`" for c in cols)
    upd  = ",".join(f"`{c}`=VALUES(`{c}`)" for c in cols if c != "id")
    cur.execute(
        f"INSERT INTO itineraries ({col_str}) VALUES ({ph}) ON DUPLICATE KEY UPDATE {upd}", vals)
    cur.close(); conn.close()

save_itinerary_to_file = save_itinerary   # backward-compat alias

def delete_itinerary(iid, user):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM itineraries WHERE id=%s AND user=%s", (iid, user))
    cur.close(); conn.close()

def admin_delete_itinerary(iid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM itineraries WHERE id=%s", (iid,))
    cur.close(); conn.close()

def get_user_trip_count(username):
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM itineraries WHERE user=%s", (username,))
    count = cur.fetchone()[0]; cur.close(); conn.close()
    return count

def get_system_stats():
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users"); uc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM admins"); ac = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM itineraries"); tc = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(SUM(budget),0) FROM itineraries"); tb = float(cur.fetchone()[0])
    cur.close(); conn.close()
    return uc, ac, tc, tb

def get_user_itineraries(u):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM itineraries WHERE user=%s ORDER BY created_at ASC", (u,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [_row_to_rec(r) for r in rows]

def load_all_itineraries():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM itineraries ORDER BY created_at DESC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [_row_to_rec(r) for r in rows]

# ════════════════════════════════════════════════════════════════════════════
# EXPENSE FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════
def save_expense(e):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (id,itinerary_id,user,date,category,description,amount) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (e["id"],e["itinerary_id"],e["user"],e["date"],e["category"],e["description"],e["amount"]))
    cur.close(); conn.close()

def delete_expense(eid):
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM expenses WHERE id=%s", (eid,))
    cur.close(); conn.close()

def get_trip_expenses(iid):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM expenses WHERE itinerary_id=%s ORDER BY date ASC", (iid,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]

def get_user_expenses(u):
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM expenses WHERE user=%s", (u,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]

def load_expenses():
    conn = get_db(); cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM expenses")
    rows = cur.fetchall(); cur.close(); conn.close()
    return [dict(r) for r in rows]

# ════════════════════════════════════════════════════════════════════════════
# AI
# ════════════════════════════════════════════════════════════════════════════
def ai_call(prompt,system="You are an expert travel planner.",max_tokens=2500):
    try:
        client=OpenAI(api_key=OPENAI_API_KEY)
        r=client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            max_tokens=max_tokens)
        return r.choices[0].message.content
    except Exception as e: return f"[AI Error: {e}]"

def generate_itinerary_ai(dest,days,budget,style,acts,start,
                          accommodation="Any",transport="Any",
                          meal_pref="No preference",pace="Moderate",
                          fitness="Moderate",must_visit="",avoid="",
                          lang_tips=False,visa_info=False,travelers=1,
                          group_type="Solo",kids_ages="",eco=False,pet=False,
                          day_start="Standard (8 am)",restaurant_meals=2,
                          nightlife=False,off_peak=False,
                          budget_priority="Balanced",currency="USD",
                          emergency_tips=False,health_tips=False,
                          photo_spots=False,day_trips=False,local_events=False,
                          trip_theme="General"):
    adv_lines = []
    if accommodation != "Any":  adv_lines.append(f"Accommodation: {accommodation}")
    if transport     != "Any":  adv_lines.append(f"Transport: {transport}")
    if meal_pref     != "No preference": adv_lines.append(f"Meal preference: {meal_pref}")
    adv_lines.append(f"Trip pace: {pace} | Fitness level: {fitness}")
    adv_lines.append(f"Group: {group_type} ({travelers} people){', kids ages: '+kids_ages if kids_ages else ''}")
    if trip_theme != "General": adv_lines.append(f"Trip theme: {trip_theme}")
    adv_lines.append(f"Day starts: {day_start} | Restaurant meals per day: {restaurant_meals}")
    adv_lines.append(f"Budget priority: {budget_priority} | Show costs in: {currency}")
    if nightlife:  adv_lines.append("Include evening/nightlife recommendations.")
    if off_peak:   adv_lines.append("Prefer off-peak timings for attractions to avoid crowds.")
    if eco:        adv_lines.append("Prefer eco-friendly and sustainable options throughout.")
    if pet:        adv_lines.append("Trip is pet-friendly — include pet-welcoming venues.")
    if must_visit.strip(): adv_lines.append(f"Must-visit: {must_visit}")
    if avoid.strip():      adv_lines.append(f"Avoid: {avoid}")
    if photo_spots: adv_lines.append("Each day include the best photography spot with timing tip.")
    if day_trips:   adv_lines.append("Suggest one nearby day-trip option per 3 days of travel.")
    adv_block = ("\n".join(adv_lines) + "\n") if adv_lines else ""
    extras = ""
    if lang_tips:      extras += "\n\n**Useful Local Phrases** — 8 key phrases: English | Local | Pronunciation."
    if visa_info:      extras += "\n\n**Visa & Entry Requirements** — general tips and common requirements for this destination."
    if emergency_tips: extras += "\n\n**Safety & Emergency Contacts** — local emergency numbers, safety tips, nearest hospital advice."
    if health_tips:    extras += "\n\n**Health & Vaccinations** — recommended vaccinations, health precautions, and medical tips for this destination."
    if local_events:   extras += f"\n\n**Local Festivals & Events** — note any festivals or events likely occurring in {dest} around {start}."
    return ai_call(
        f"Create a detailed day-by-day travel itinerary for {dest}.\n"
        f"Duration: {days} days starting {start}\n"
        f"Budget: ${budget:,.2f} {currency} | Style: {style} | Interests: {acts}\n"
        f"{adv_block}"
        "Format each day as:\n**Day N - [Theme]**\n"
        "- Morning: [activity + cost]\n- Afternoon: [activity + cost]\n"
        "- Evening: [activity + cost]\n- Daily spend: $XX\n\n"
        f"End with **Budget Summary** table.{extras}",max_tokens=3500)
def generate_packing_list(dest,days,style,acts):
    return ai_call(f"Packing list for {days} days in {dest} as {style}. Activities: {acts}. "
                   "Group: Clothing, Toiletries, Electronics, Documents, Medications, Misc. "
                   "Each item on its own line with checkbox ☐.")
def generate_budget_tips(dest,budget,style):
    return ai_call(f"Give 10 money-saving tips for {dest} on ${budget:,.0f} as {style}. "
                   "Cover: accommodation, food, transport, activities, hidden costs.")
def generate_surprise(style,budget,acts):
    return ai_call(f"Suggest ONE surprise destination for {style} traveler with ${budget:,.0f} who enjoys {acts}. "
                   "Include: destination, why perfect, best time, 3-day sample itinerary.")
def generate_phrases(dest):
    return ai_call(f"Give 20 essential travel phrases for {dest}. "
                   "Format: English | Local | Pronunciation. "
                   "Include: greetings, directions, food, shopping, emergencies.")

def generate_hotel_suggestions(dest, budget, style, travelers, accommodation_pref, currency="USD"):
    return ai_call(
        f"Suggest 6 real, highly-rated hotels or stays in {dest} for {travelers} traveler(s). "
        f"Total trip budget: {budget:,.0f} {currency}. Travel style: {style}. "
        f"Preferred accommodation: {accommodation_pref}.\n"
        "For EACH hotel provide:\n"
        "**[Hotel Name]** — [Star rating] stars\n"
        "- Price per night: approx [amount] USD\n"
        "- Location: [area/neighbourhood]\n"
        "- Best for: [type of traveler]\n"
        "- Highlights: [2-3 key features]\n"
        "- Booking: [website if widely known, e.g. booking.com search tip]\n\n"
        "Mix budget, mid-range and premium options. Include real places only.",
        max_tokens=1800)

def generate_restaurant_suggestions(dest, meal_pref, style, travelers, currency="USD"):
    return ai_call(
        f"Suggest 8 must-visit restaurants or eateries in {dest} for {travelers} traveler(s). "
        f"Travel style: {style}. Dietary preference: {meal_pref}.\n"
        "For EACH restaurant provide:\n"
        "**[Restaurant Name]** — [Cuisine type]\n"
        "- Price range: [$/$$/$$$]\n"
        "- Location: [area/neighbourhood]\n"
        "- Must-try dish: [dish name]\n"
        "- Best time to visit: [meal / hours]\n"
        "- Why go: [1-line reason]\n\n"
        "Mix street food, casual dining and fine dining. Include real places only.",
        max_tokens=1800)

def generate_attraction_suggestions(dest, style, acts, days):
    return ai_call(
        f"Suggest the top 10 attractions and experiences in {dest} for a {style} traveler "
        f"interested in {acts} visiting for {days} days.\n"
        "For EACH attraction:\n"
        "**[Attraction Name]**\n"
        "- Type: [museum / nature / food / culture / adventure / etc.]\n"
        "- Best time to visit: [time of day / season]\n"
        "- Approx entry cost: [amount or free]\n"
        "- Time needed: [X hours]\n"
        "- Insider tip: [one practical tip]\n\n"
        "Include both famous and hidden-gem options.",
        max_tokens=1800)

# ════════════════════════════════════════════════════════════════════════════
# WEATHER
# ════════════════════════════════════════════════════════════════════════════
def get_weather(city):
    try:
        r=requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric",timeout=5)
        if r.status_code==200:
            d=r.json()
            return {"temp":round(d["main"]["temp"]),"feels":round(d["main"]["feels_like"]),
                    "humidity":d["main"]["humidity"],"desc":d["weather"][0]["description"].title(),
                    "wind":round(d["wind"]["speed"]*3.6,1)}
    except: pass
    return None
def get_forecast(city):
    try:
        r=requests.get(f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric&cnt=24",timeout=5)
        if r.status_code==200:
            seen,result=set(),[]
            for item in r.json()["list"]:
                day=item["dt_txt"][:10]
                if day not in seen:
                    seen.add(day)
                    result.append({"date":day,"max":round(item["main"]["temp_max"]),
                                   "min":round(item["main"]["temp_min"]),
                                   "desc":item["weather"][0]["description"].title()})
            return result[:5]
    except: pass
    return []

# ════════════════════════════════════════════════════════════════════════════
# PDF
# ════════════════════════════════════════════════════════════════════════════
def build_pdf(rec,expenses=None):
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=letter,leftMargin=50,rightMargin=50,topMargin=50,bottomMargin=50)
    styles=getSampleStyleSheet()
    def S(n,**kw): return ParagraphStyle(n,parent=styles["Normal"],**kw)
    ts =S("T",textColor=colors.HexColor("#1b5e20"),fontSize=22,spaceAfter=6,fontName="Helvetica-Bold")
    hs =S("H",textColor=colors.HexColor("#2e7d32"),fontSize=13,spaceAfter=4,fontName="Helvetica-Bold",spaceBefore=10)
    h2s=S("H2",textColor=colors.HexColor("#2e7d32"),fontSize=11,spaceAfter=3,fontName="Helvetica-Bold",spaceBefore=6)
    bs =S("B",fontSize=9,leading=14,spaceAfter=2)
    bls=S("BL",fontSize=9,leading=14,leftIndent=15,spaceAfter=1)
    ss =S("S",textColor=colors.HexColor("#555"),fontSize=9,spaceAfter=2)
    story=[]
    story.append(Paragraph("AI Travel Itinerary Planner",ts))
    story.append(HRFlowable(width="100%",thickness=2,color=colors.HexColor("#1b5e20")))
    story.append(Spacer(1,8))
    summary=[["Destination",rec.get("destination","")],
             ["Duration",f"{rec.get('days','')} days from {rec.get('start_date','N/A')}"],
             ["Budget",f"${rec.get('budget',0):,.2f} USD"],
             ["Travel Style",rec.get("travel_type","")],
             ["Activities",rec.get("activities","")],
             ["Generated",rec.get("saved_on",str(date.today()))]]
    tbl=Table(summary,colWidths=[1.5*inch,5*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#c8e6c9")),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.HexColor("#e8f5e9"),colors.HexColor("#f0f4f8")]),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#a5d6a7")),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(tbl); story.append(Spacer(1,12))
    story.append(Paragraph("Your Day-by-Day Itinerary",hs))
    story.append(HRFlowable(width="100%",thickness=1,color=colors.HexColor("#a5d6a7")))
    story.append(Spacer(1,6))
    for line in rec.get("itinerary","").split("\n"):
        line=line.strip()
        if not line: story.append(Spacer(1,4)); continue
        clean=line.replace("**","").replace("##","").replace("*","")
        if re.match(r"^Day \d+",clean,re.IGNORECASE): story.append(Paragraph(clean,h2s))
        elif clean.startswith("-") or clean.startswith("*"): story.append(Paragraph(clean.lstrip("-* "),bls))
        elif "budget summary" in clean.lower(): story.append(Paragraph(clean,hs))
        else: story.append(Paragraph(clean,bs))
    if rec.get("packing_list"):
        story.append(Spacer(1,12)); story.append(Paragraph("Packing List",hs))
        story.append(HRFlowable(width="100%",thickness=1,color=colors.HexColor("#a5d6a7")))
        for line in rec["packing_list"].split("\n"):
            line=line.strip()
            if not line: story.append(Spacer(1,3))
            elif line.endswith(":"): story.append(Paragraph(line,h2s))
            else: story.append(Paragraph(line,bls))
    if expenses:
        story.append(Spacer(1,12)); story.append(Paragraph("Expense Summary",hs))
        edata=[["Date","Category","Description","Amount"]]; total=0
        for e in expenses:
            edata.append([e.get("date",""),e.get("category",""),e.get("description",""),f"${e.get('amount',0):.2f}"])
            total+=e.get("amount",0)
        edata.append(["","","TOTAL",f"${total:.2f}"])
        et=Table(edata,colWidths=[1*inch,1.3*inch,3.2*inch,1*inch])
        et.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2e7d32")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#e8f5e9")),
            ("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#a5d6a7")),
            ("ROWBACKGROUNDS",(0,1),(-1,-2),[colors.white,colors.HexColor("#f5f5f5")]),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story.append(et)
    story.append(Spacer(1,20))
    story.append(HRFlowable(width="100%",thickness=1,color=colors.HexColor("#ccc")))
    story.append(Paragraph(f"Generated by AI Travel Itinerary Planner • {date.today()} • Have a wonderful trip!",ss))
    doc.build(story); buf.seek(0); return buf.read()

# ════════════════════════════════════════════════════════════════════════════
# EMAIL
# ════════════════════════════════════════════════════════════════════════════
def send_email(to,rec,pdf):
    try:
        msg=MIMEMultipart(); msg["From"]=SMTP_USER_ADDR; msg["To"]=to
        msg["Subject"]=f"Your Travel Itinerary - {rec.get('destination','Trip')}"
        body=(f"Hi {rec.get('user','Traveler')},\n\nYour itinerary for {rec.get('destination')} is attached.\n\n"
              f"Destination: {rec.get('destination')}\nDuration: {rec.get('days')} days\n"
              f"Budget: ${rec.get('budget',0):,.2f} USD\n\nHave a wonderful trip!\nAI Travel Planner")
        msg.attach(MIMEText(body,"plain"))
        part=MIMEBase("application","octet-stream"); part.set_payload(pdf); encoders.encode_base64(part)
        safe=rec.get("destination","trip").replace(" ","_").replace(",","")
        part.add_header("Content-Disposition",f'attachment; filename="Itinerary_{safe}.pdf"')
        msg.attach(part)
        with smtplib.SMTP(SMTP_HOST,SMTP_PORT) as s:
            s.starttls(); s.login(SMTP_USER_ADDR,SMTP_PASS); s.sendmail(SMTP_USER_ADDR,to,msg.as_string())
        return True,"Email sent!"
    except Exception as e: return False,f"Email failed: {e}"

def send_verification_email(to_email, full_name, token):
    """Send an account verification email containing a one-time link."""
    try:
        app_url   = os.getenv("APP_URL", "http://localhost:8501")
        link      = f"{app_url}/?verify={token}"
        msg       = MIMEMultipart("alternative")
        msg["From"]    = SMTP_USER_ADDR
        msg["To"]      = to_email
        msg["Subject"] = "Verify your AI Travel Planner account"

        plain = (
            f"Hi {full_name},\n\n"
            f"Welcome to AI Travel Planner! Please verify your email by opening this link:\n\n"
            f"{link}\n\n"
            f"If you did not create an account, you can ignore this email.\n\n"
            f"— AI Travel Planner"
        )
        html = f"""<html><body style="margin:0;padding:0;background:#f0fff4;font-family:Arial,sans-serif">
<div style="max-width:520px;margin:40px auto;background:#ffffff;border-radius:16px;
     overflow:hidden;box-shadow:0 4px 24px rgba(27,94,32,0.12)">
  <div style="background:linear-gradient(135deg,#1b5e20,#2e7d32);padding:32px 32px 24px">
    <h1 style="margin:0;color:#ffffff;font-size:26px;font-weight:800">AI Travel Planner</h1>
    <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:14px">Email Verification</p>
  </div>
  <div style="padding:32px">
    <h2 style="margin:0 0 12px;color:#1b5e20;font-size:20px">Hi {full_name},</h2>
    <p style="color:#475569;line-height:1.7;margin:0 0 24px">
      Thanks for signing up! Click the button below to verify your email address
      and activate your account.
    </p>
    <div style="text-align:center;margin:0 0 28px">
      <a href="{link}" style="background:#1b5e20;color:#ffffff;text-decoration:none;
         padding:14px 36px;border-radius:10px;font-weight:700;font-size:16px;
         display:inline-block;letter-spacing:0.3px">Verify My Email</a>
    </div>
    <p style="color:#94a3b8;font-size:13px;line-height:1.6;margin:0">
      Or copy this link into your browser:<br>
      <span style="color:#1b5e20;word-break:break-all">{link}</span>
    </p>
  </div>
  <div style="background:#f8fafc;padding:18px 32px;border-top:1px solid #e2e8f0">
    <p style="margin:0;color:#94a3b8;font-size:12px">
      If you did not create an account, you can safely ignore this email.
    </p>
  </div>
</div>
</body></html>"""

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html,  "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER_ADDR, SMTP_PASS)
            s.sendmail(SMTP_USER_ADDR, to_email, msg.as_string())
        return True, "Verification email sent."
    except Exception as e:
        return False, str(e)

# ════════════════════════════════════════════════════════════════════════════
# CHARTS
# ════════════════════════════════════════════════════════════════════════════
def pie_chart(budget):
    labels=["Accommodation","Food","Transport","Activities","Misc"]
    values=[round(budget*f,2) for f in [0.35,0.25,0.15,0.20,0.05]]
    fig=go.Figure(go.Pie(labels=labels,values=values,hole=0.45,
        marker_colors=["#1b5e20","#2e7d32","#f57f17","#6a1b9a","#37474f"],textfont=dict(size=14)))
    fig.update_layout(title=dict(text="Budget Breakdown",font=dict(size=18,color="#1b5e20")),
        legend=dict(font=dict(size=14)),margin=dict(t=55,b=10,l=10,r=10),height=360,
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    return fig

def expense_chart(expenses,budget,currency="USD"):
    if not expenses: return None
    cats={}; sym=csym(currency)
    for e in expenses: cats[e.get("category","Other")]=cats.get(e.get("category","Other"),0)+e.get("amount",0)
    fig=go.Figure()
    fig.add_trace(go.Bar(x=list(cats.keys()),y=list(cats.values()),marker_color="#2e7d32",
        text=[f"{sym}{v:,.0f}" for v in cats.values()],textposition="outside",textfont=dict(size=14)))
    fig.add_hline(y=budget,line_dash="dash",line_color="#ef4444",
        annotation_text=f"Budget {sym}{budget:,.0f}",annotation_font=dict(size=14,color="#ef4444"))
    fig.update_layout(title=dict(text="Spending vs Budget",font=dict(size=18,color="#1b5e20")),
        yaxis_title=currency,xaxis=dict(tickfont=dict(size=14)),yaxis=dict(tickfont=dict(size=14)),
        height=360,margin=dict(t=55,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    return fig

def timeline_chart(trips):
    if not trips: return None
    data=[]
    for r in trips:
        start=r.get("start_date") or r.get("saved_on") or str(date.today())
        try:
            s=datetime.strptime(start,"%Y-%m-%d")
            data.append(dict(Task=r.get("destination","?"),Start=start,
                Finish=str(date.fromordinal(s.toordinal()+max(r.get("days",1),1))),Budget=r.get("budget",0)))
        except: pass
    if not data: return None
    fig=px.timeline(data,x_start="Start",x_end="Finish",y="Task",color="Budget",
        title="Trip Timeline",color_continuous_scale="Greens")
    fig.update_layout(height=max(260,70*len(data)+80),
        yaxis=dict(tickfont=dict(size=14)),xaxis=dict(tickfont=dict(size=14)),
        title_font=dict(size=18,color="#1b5e20"),margin=dict(t=55,b=10),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    return fig

# ════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={'Get Help':None,'Report a bug':None,'About':None}
)

# Initialise MySQL tables and seed defaults (runs once per session)
try:
    init_db()
except mysql.connector.Error as e:
    st.error(f"**Database connection failed:** {e}")
    st.info("**How to fix:** Make sure MySQL is running, then set `DB_HOST`, `DB_USER`, and `DB_PASS` "
            "as environment variables (or edit the defaults in the config section of app.py).")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# MASTER CSS  — fixes sidebar buttons, text visibility, content size
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── RESET ─────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 16px !important;
    line-height: 1.6 !important;
}
[data-testid="stAppViewContainer"] { background: #f0fff4 !important; }
[data-testid="stToolbar"]          { display: none !important; }

/* ── MAIN CONTENT AREA ──────────────────────────────────────────────────── */
.block-container {
    padding: 2.5rem 3rem 3rem 3rem !important;
    max-width: 1500px !important;
}

/* ── TYPOGRAPHY — Big, Bold, Visible ───────────────────────────────────── */
h1 {
    font-size: 36px !important;
    font-weight: 900 !important;
    color: #1b5e20 !important;
    letter-spacing: -0.8px !important;
    margin: 0 0 6px 0 !important;
    line-height: 1.2 !important;
}
h2 {
    font-size: 28px !important;
    font-weight: 800 !important;
    color: #1b5e20 !important;
    margin: 0 0 6px 0 !important;
    line-height: 1.2 !important;
}
h3 {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #2e7d32 !important;
    margin: 0 0 6px 0 !important;
}
h4 {
    font-size: 18px !important;
    font-weight: 700 !important;
    color: #2e7d32 !important;
    margin: 0 0 6px 0 !important;
}
/* ── BASE TEXT — main content only, never overrides dark-bg areas ─────── */
[data-testid="stMain"] p,
[data-testid="stMain"] li,
[data-testid="stMain"] label {
    font-size: 16px !important;
    color: #1e293b !important;
}
/* Streamlit markdown containers — scoped to main area only, never touches sidebar */
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] li {
    font-size: 16px !important;
    color: #1e293b !important;
    line-height: 1.75 !important;
}
/* ── AUTH HERO — dark green bg, all text must be WHITE ───────────────── */
/* Higher specificity: attribute(1) + class(1) + wildcard = beats attribute(1)+element(1) */
[data-testid="stMarkdownContainer"] .auth-hero,
[data-testid="stMarkdownContainer"] .auth-hero div,
[data-testid="stMarkdownContainer"] .auth-hero span,
[data-testid="stMarkdownContainer"] .auth-hero p,
[data-testid="stMarkdownContainer"] .auth-hero strong {
    color: white !important;
}
strong, b { color: #1b5e20 !important; font-weight: 700 !important; }

/* ── SIDEBAR — base styling only, no forced visibility (media queries handle that) */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 3px solid #c8e6c9 !important;
}
/* Desktop: fixed open */
@media (min-width: 1025px) {
    [data-testid="stSidebar"] {
        width: 270px !important;
        min-width: 270px !important;
        max-width: 270px !important;
        transform: translateX(0px) !important;
        visibility: visible !important;
        display: block !important;
        opacity: 1 !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        width: 270px !important;
        min-width: 270px !important;
    }
}

/* ── SIDEBAR COLLAPSED RE-OPEN BUTTON (native Streamlit) ─────────────────── */
/* Large green pill on the left edge — always clickable even if sidebar hides */
[data-testid="stSidebarCollapsedControl"] {
    position: fixed !important;
    left: 0 !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    background: #1b5e20 !important;
    border-radius: 0 16px 16px 0 !important;
    width: 48px !important;
    height: 72px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 4px 0 18px rgba(27,94,32,0.45) !important;
    z-index: 999999 !important;
    cursor: pointer !important;
}
[data-testid="stSidebarCollapsedControl"] button {
    color: #ffffff !important;
    background: transparent !important;
    border: none !important;
    width: 48px !important;
    height: 72px !important;
    min-height: unset !important;
    font-size: 24px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 16px 16px 0 !important;
    box-shadow: none !important;
    width: 100% !important;
}
[data-testid="stSidebarCollapsedControl"] button svg {
    fill: #ffffff !important;
    stroke: #ffffff !important;
    width: 22px !important;
    height: 22px !important;
}

/* ── METRIC CARD ─────────────────────────────────────────────────────────── */
.kpi-card {
    background: white;
    border-radius: 20px;
    padding: 28px 22px 22px 22px;
    box-shadow: 0 4px 20px rgba(27,94,32,0.10);
    text-align: center;
    border-top: 5px solid #2e7d32;
    transition: transform 0.22s ease, box-shadow 0.22s ease;
    height: 100%;
    position: relative;
    overflow: hidden;
}
.kpi-card::after {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 110px; height: 110px;
    background: radial-gradient(circle, rgba(46,125,50,0.07) 0%, transparent 70%);
    border-radius: 50%;
}
.kpi-card:hover { transform: translateY(-4px); box-shadow: 0 10px 32px rgba(27,94,32,0.16); }
.kpi-icon { font-size: 34px; margin-bottom: 10px; display: block; line-height: 1; }
.kpi-val  { font-size: 38px !important; font-weight: 900 !important; color: #1b5e20 !important; line-height: 1; margin: 0 !important; }
.kpi-lbl  { font-size: 14px !important; color: #64748b !important; margin-top: 8px; font-weight: 600 !important; text-transform: uppercase; letter-spacing: 0.5px; }

/* ── SECTION HEADER ──────────────────────────────────────────────────────── */
.sec-hdr {
    background: linear-gradient(90deg, #1b5e20 0%, #388e3c 100%);
    color: white !important;
    padding: 14px 22px;
    border-radius: 14px;
    font-size: 17px !important;
    font-weight: 700 !important;
    margin-bottom: 18px;
    letter-spacing: 0.2px;
    box-shadow: 0 3px 12px rgba(27,94,32,0.22);
    display: flex;
    align-items: center;
    gap: 8px;
}
.sec-hdr * { color: white !important; font-size: 17px !important; }

 ── TRIP CARD ───────────────────────────────────────────────────────────── 
.trip-card {
    background: white;
    border-radius: 16px;
    padding: 20px 22px;
    box-shadow: 0 3px 14px rgba(27,94,32,0.09);
    margin-bottom: 14px;
    border-left: 6px solid #2e7d32;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.trip-card:hover { transform: translateX(3px); box-shadow: 0 6px 22px rgba(27,94,32,0.15); }
.trip-card h4 { font-size: 19px !important; font-weight: 700 !important; color: #1b5e20 !important; margin: 0 0 10px 0 !important; }
.trip-card p  { font-size: 15px !important; color: #475569 !important; margin: 5px 0 !important; }

/* ── WEATHER CARD ────────────────────────────────────────────────────────── */
.weather-card {
    background: linear-gradient(135deg, #1a6b1a 0%, #43a047 65%, #66bb6a 100%);
    color: white;
    border-radius: 20px;
    padding: 28px 32px;
    box-shadow: 0 8px 28px rgba(27,94,32,0.28);
    position: relative;
    overflow: hidden;
}
.weather-card::before {
    content: '';
    position: absolute;
    top: -30px; right: -30px;
    width: 160px; height: 160px;
    background: rgba(255,255,255,0.07);
    border-radius: 50%;
}
.wc-title  { font-size: 15px !important; font-weight: 700 !important; opacity: 0.9; margin-bottom: 8px; color: white !important; }
.wc-temp   { font-size: 64px !important; font-weight: 900 !important; color: white !important; line-height: 1; margin: 4px 0 8px 0; }
.wc-desc   { font-size: 18px !important; color: white !important; opacity: 0.96; font-weight: 500; }
.wc-detail { font-size: 15px !important; color: white !important; opacity: 0.85; margin-top: 8px; }

/* ── ITINERARY BOX ───────────────────────────────────────────────────────── */
.itin-box {
    background: white;
    border-radius: 16px;
    padding: 26px 30px;
    box-shadow: 0 3px 16px rgba(0,0,0,0.07);
    line-height: 1.85;
    font-size: 16px !important;
    max-height: 540px;
    overflow-y: auto;
    border: 2px solid #e2e8f0;
    color: #1e293b !important;
}
.itin-box * { font-size: 16px !important; color: #1e293b !important; }

/* ── LOGIN / AUTH PAGE ───────────────────────────────────────────────────── */
.auth-root {
    display: flex;
    min-height: 100vh;
    width: 100%;
    background: #f0fff4;
    align-items: stretch;
}
.auth-hero {
    flex: 1;
    background: linear-gradient(145deg, #064e06 0%, #1b5e20 45%, #2e7d32 100%);
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 52px;
    color: white;
    position: relative;
    overflow: hidden;
}
.auth-hero::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 340px; height: 340px;
    background: rgba(255,255,255,0.06);
    border-radius: 50%;
}
.auth-hero::after {
    content: '';
    position: absolute;
    bottom: -60px; left: -60px;
    width: 260px; height: 260px;
    background: rgba(255,255,255,0.04);
    border-radius: 50%;
}
.auth-hero-icon  { font-size: 58px; margin-bottom: 22px; display: block; }
.auth-hero-title { font-size: 38px !important; font-weight: 900 !important; color: white !important;
                   line-height: 1.15; margin: 0 0 12px 0 !important; letter-spacing: -1px; }
.auth-hero-sub   { font-size: 17px !important; color: rgba(255,255,255,0.82) !important;
                   margin-bottom: 44px; line-height: 1.65; }
.auth-feature    { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.auth-feature-dot { width: 8px; height: 8px; border-radius: 50%;
                    background: rgba(255,255,255,0.6); flex-shrink: 0; }
.auth-feature-txt { font-size: 15px !important; color: rgba(255,255,255,0.88) !important; }
.auth-card {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 52px;
    background: white;
    max-width: 520px;
}
.auth-card-title { font-size: 28px !important; font-weight: 800 !important;
                   color: #1b5e20 !important; margin: 0 0 6px 0 !important; }
.auth-card-sub   { font-size: 15px !important; color: #64748b !important; margin-bottom: 32px; }
.auth-divider    { display: flex; align-items: center; gap: 14px; margin: 20px 0; }
.auth-divider hr { flex: 1; border: none; border-top: 1.5px solid #e2e8f0; margin: 0; }
.auth-divider span { font-size: 13px !important; color: #94a3b8 !important; white-space: nowrap; }
.cred-box {
    background: #f1f8e9;
    border-radius: 12px;
    padding: 14px 18px;
    margin-top: 18px;
    border: 1.5px solid #c8e6c9;
}
.cred-box .cred-title { font-size: 13px !important; font-weight: 700 !important;
                        color: #1b5e20 !important; margin-bottom: 5px; display: block;
                        text-transform: uppercase; letter-spacing: 0.5px; }
.cred-box .cred-info  { font-size: 14px !important; color: #334155 !important; }
/* Admin portal badge */
.admin-badge {
    background: linear-gradient(135deg, #064e06, #1b5e20);
    color: white;
    padding: 4px 12px;
    border-radius: 99px;
    font-size: 12px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px;
    display: inline-block;
    margin-bottom: 16px;
}
/* Hide default streamlit tab styling on login and use clean pill tabs */
.stTabs [data-baseweb="tab-list"] {
    background: #f1f5f9 !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
    border-bottom: none !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    color: #64748b !important;
    background: transparent !important;
    border: none !important;
    padding: 10px 24px !important;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #1b5e20 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.10) !important;
}

/* ── FORMS ───────────────────────────────────────────────────────────────── */
[data-testid="stTextInput"] > div > div > input,
[data-testid="stNumberInput"] > div > div > input,
[data-testid="stTextArea"] > div > textarea {
    font-size: 16px !important;
    font-family: 'Inter', sans-serif !important;
    border-radius: 12px !important;
    border: 2px solid #c8e6c9 !important;
    padding: 12px 16px !important;
    background: #f9fdf9 !important;
    color: #1e293b !important;
    caret-color: #1b5e20 !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    height: auto !important;
}
[data-testid="stSelectbox"] > div > div {
    font-size: 16px !important;
    border-radius: 12px !important;
    border: 2px solid #c8e6c9 !important;
    background: #ffffff !important;
    color: #1e293b !important;
}
/* Dropdown popup — white background, dark text */
[data-baseweb="popover"],
[data-baseweb="popover"] * {
    background: #ffffff !important;
    color: #1e293b !important;
}
[data-baseweb="option"] {
    background: #ffffff !important;
    color: #1e293b !important;
    font-size: 15px !important;
}
[data-baseweb="option"]:hover,
[data-baseweb="option"][aria-selected="true"] {
    background: #e8f5e9 !important;
    color: #1b5e20 !important;
}
/* Selected value text in closed selectbox */
[data-testid="stSelectbox"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] span {
    color: #1e293b !important;
}
[data-baseweb="select"] > div {
    background: #ffffff !important;
    color: #1e293b !important;
}
[data-testid="stTextInput"] > div > div > input:focus,
[data-testid="stNumberInput"] > div > div > input:focus,
[data-testid="stTextArea"] > div > textarea:focus {
    border-color: #2e7d32 !important;
    box-shadow: 0 0 0 4px rgba(46,125,50,0.13) !important;
    background: white !important;
    outline: none !important;
}
/* Form labels */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label,
label {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #1b5e20 !important;
    margin-bottom: 5px !important;
    font-family: 'Inter', sans-serif !important;
}
/* Date input */
[data-testid="stDateInput"] input {
    font-size: 16px !important;
    border-radius: 12px !important;
    border: 2px solid #c8e6c9 !important;
    padding: 10px 14px !important;
    background: #f9fdf9 !important;
    color: #1e293b !important;
}

/* ── BUTTONS (main content) ──────────────────────────────────────────────── */
.stButton > button {
    font-family: 'Inter', sans-serif !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    padding: 12px 24px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    letter-spacing: 0.1px !important;
    background: linear-gradient(135deg, #1a6b1a, #388e3c) !important;
    color: white !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(27,94,32,0.25) !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(0,0,0,0.15) !important;
}
/* Primary generate button */
[data-testid="stForm"] .stButton > button[kind="primaryFormSubmit"],
[data-testid="stForm"] .stFormSubmitButton > button {
    background: linear-gradient(135deg, #1a6b1a, #388e3c) !important;
    color: white !important;
    font-size: 17px !important;
    padding: 14px 24px !important;
    border: none !important;
    box-shadow: 0 4px 16px rgba(27,94,32,0.30) !important;
}
.stDownloadButton > button {
    font-size: 16px !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg,#1a6b1a,#388e3c) !important;
    color: white !important;
    padding: 12px 22px !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(27,94,32,0.28) !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg,#1b5e20,#2e7d32) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 22px rgba(27,94,32,0.36) !important;
}

/* ── TABS ────────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] { gap: 6px; border-bottom: 2px solid #e8f5e9; }
[data-testid="stTabs"] [role="tab"] {
    font-size: 16px !important;
    font-weight: 600 !important;
    padding: 12px 22px !important;
    border-radius: 10px 10px 0 0 !important;
    color: #64748b !important;
    background: transparent !important;
    border: none !important;
    transition: color 0.2s, background 0.2s !important;
}
[data-testid="stTabs"] [role="tab"]:hover { color: #2e7d32 !important; background: #f1f8e9 !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #1b5e20 !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #1b5e20 !important;
    background: #f1f8e9 !important;
}

/* ── EXPANDERS ───────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 2px solid #c8e6c9 !important;
    border-radius: 16px !important;
    margin-bottom: 12px !important;
    background: white !important;
    box-shadow: 0 2px 8px rgba(27,94,32,0.06) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] summary {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #1b5e20 !important;
    padding: 16px 20px !important;
    background: #f9fdf9 !important;
    cursor: pointer !important;
}
[data-testid="stExpander"] summary:hover { background: #f1f8e9 !important; }
[data-testid="stExpander"] summary p { font-size: 17px !important; color: #1b5e20 !important; font-weight: 700 !important; }

/* ── METRICS (native st.metric) ─────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: white !important;
    border-radius: 16px !important;
    padding: 20px !important;
    box-shadow: 0 3px 14px rgba(27,94,32,0.09) !important;
    border-top: 4px solid #2e7d32 !important;
}
[data-testid="stMetricValue"] { font-size: 30px !important; font-weight: 800 !important; color: #1b5e20 !important; }
[data-testid="stMetricLabel"] { font-size: 14px !important; font-weight: 700 !important; color: #475569 !important; text-transform: uppercase; letter-spacing: 0.4px; }
[data-testid="stMetricDelta"] { font-size: 13px !important; }

/* ── ALERTS / INFO BOXES ─────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    font-size: 16px !important;
    border-radius: 14px !important;
    padding: 16px 20px !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] div,
[data-testid="stAlert"] span { font-size: 16px !important; color: inherit !important; }

/* ── WIDGET LABELS AND NATIVE COMPONENT TEXT ─────────────────────────────── */
[data-testid="stWidgetLabel"] p { color: #1b5e20 !important; }
[data-testid="stTabs"] [role="tab"] { color: #64748b !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #1b5e20 !important; }
[data-testid="stExpander"] summary p { color: #1b5e20 !important; }
code { color: #1b5e20 !important; background: #f1f8e9 !important; padding: 2px 6px !important; border-radius: 6px !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] span { color: #1e293b !important; }
[data-testid="stSpinner"] p { color: #475569 !important; }

/* ── PROGRESS BAR ────────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div {
    border-radius: 99px !important;
    height: 14px !important;
}

/* ── CHECKBOX ────────────────────────────────────────────────────────────── */
[data-testid="stCheckbox"] label p { font-size: 16px !important; color: #1e293b !important; font-weight: 600 !important; }

/* ── CAPTIONS ────────────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p,
.stCaption { font-size: 14px !important; color: #64748b !important; }

/* ── DIVIDERS ────────────────────────────────────────────────────────────── */
hr { border-color: #e8f5e9 !important; margin: 20px 0 !important; }

/* ── CODE BLOCKS ─────────────────────────────────────────────────────────── */
code, pre { font-size: 14px !important; border-radius: 12px !important; }

/* ── CUSTOM SCROLLBAR ────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 99px; }
::-webkit-scrollbar-thumb { background: #a5d6a7; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #2e7d32; }

/* ── FORECAST CARD ───────────────────────────────────────────────────────── */
.fc-card {
    background: white;
    border-radius: 16px;
    padding: 20px 14px;
    text-align: center;
    box-shadow: 0 3px 12px rgba(27,94,32,0.10);
    border-top: 4px solid #2e7d32;
    transition: transform 0.2s;
}
.fc-card:hover { transform: translateY(-3px); }
.fc-date { font-size: 15px !important; font-weight: 700 !important; color: #1b5e20 !important; }
.fc-temp-hi { font-size: 30px !important; font-weight: 900 !important; color: #2e7d32 !important; margin: 8px 0 4px 0; }
.fc-temp-lo { font-size: 16px !important; font-weight: 600 !important; color: #64748b !important; }
.fc-desc    { font-size: 13px !important; color: #94a3b8 !important; margin-top: 6px; }

/* ── INFO BOX ────────────────────────────────────────────────────────────── */
.info-box {
    background: white;
    border-radius: 18px;
    padding: 44px 32px;
    text-align: center;
    box-shadow: 0 3px 18px rgba(27,94,32,0.08);
    border: 2px dashed #c8e6c9;
}
.info-box .ib-icon  { font-size: 58px; margin-bottom: 14px; }
.info-box .ib-title { font-size: 22px !important; font-weight: 800 !important; color: #1b5e20 !important; margin-bottom: 10px; }
.info-box .ib-sub   { font-size: 16px !important; color: #64748b !important; line-height: 1.7; }

/* ══════════════════════════════════════════════════════════════════════════
   RESPONSIVE  —  Tablet ≤1024px  |  Mobile ≤768px  |  Small ≤480px
   ══════════════════════════════════════════════════════════════════════════ */

/* Hamburger button — hidden on desktop, shown by JS on mobile */
#_mob_ham {
    display: none;
    position: fixed;
    top: 10px; left: 10px;
    z-index: 100002;
    width: 44px; height: 44px;
    border-radius: 10px;
    background: #1b5e20;
    border: none;
    color: white;
    font-size: 22px;
    cursor: pointer;
    align-items: center;
    justify-content: center;
    box-shadow: 0 3px 14px rgba(0,0,0,0.32);
    transition: background 0.2s;
}
/* Overlay behind open sidebar */
#_mob_overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: 99998;
    backdrop-filter: blur(1px);
}

/* ── Tablet  769–1024px ──────────────────────────────────────────────────── */
@media (max-width: 1024px) {
    [data-testid="stSidebar"] {
        width: 230px !important; min-width: 230px !important; max-width: 230px !important;
        transform: translateX(0) !important; visibility: visible !important;
        display: block !important; opacity: 1 !important;
    }
    [data-testid="stSidebar"] > div:first-child { width: 230px !important; min-width: 230px !important; }
    .block-container { padding: 1.2rem 1.2rem 2rem 1.2rem !important; }
    h1 { font-size: 24px !important; } h2 { font-size: 20px !important; } h3 { font-size: 17px !important; }
    .kpi-val { font-size: 24px !important; } .kpi-card { padding: 13px 11px !important; }
    .stButton > button { font-size: 14px !important; padding: 10px 14px !important; }
    /* Tablet: keep auth split-screen */
    .auth-hero { min-height: 80vh !important; }
    .auth-hero-title { font-size: 30px !important; }
}

/* ── Mobile  ≤768px ──────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    /* Show hamburger on mobile */
    #_mob_ham { display: flex !important; }

    /* Hide Streamlit's own sidebar toggle (we use our hamburger instead) */
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }

    /* Sidebar: fixed, HIDDEN off-screen by default */
    [data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important; left: 0 !important;
        height: 100vh !important;
        width: 250px !important; min-width: 250px !important; max-width: 250px !important;
        z-index: 99999 !important; overflow-y: auto !important;
        transform: translateX(-260px) !important;     /* hidden off-screen */
        transition: transform 0.28s cubic-bezier(.4,0,.2,1) !important;
        visibility: visible !important; display: block !important; opacity: 1 !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] > div:first-child { width: 250px !important; min-width: 250px !important; }

    /* Sidebar OPEN state — toggled by JS adding .mob-open class */
    [data-testid="stSidebar"].mob-open {
        transform: translateX(0) !important;
        box-shadow: 6px 0 36px rgba(0,0,0,0.28) !important;
    }

    /* Main content: full viewport width */
    [data-testid="stAppViewContainer"] { flex-direction: column !important; }
    section[data-testid="stMain"], [data-testid="stMain"] {
        flex: 1 1 100% !important;
        width: 100vw !important; max-width: 100vw !important;
        margin-left: 0 !important; padding-left: 0 !important; min-width: 0 !important;
    }
    /* Extra top padding so content clears the hamburger button */
    .block-container {
        padding: 58px 0.8rem 2rem 0.8rem !important;
        max-width: 100% !important; margin: 0 !important;
    }

    /* ── Stack all app columns on mobile ── */
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: 0 0 100% !important;
        width: 100% !important; max-width: 100% !important; min-width: 0 !important;
    }

    /* ── AUTH pages: KEEP 50/50 split (same as web/desktop) ── */
    [data-testid="stHorizontalBlock"]:has(.auth-hero) > [data-testid="stColumn"] {
        flex: 0 0 50% !important;
        width: 50% !important; max-width: 50% !important;
    }
    /* Auth page: no top padding (no hamburger when logged out) */
    [data-testid="stHorizontalBlock"]:has(.auth-hero) ~ * .block-container,
    .auth-hero ~ .block-container { padding-top: 1rem !important; }

    /* Auth hero responsive */
    .auth-hero { min-height: 70vh !important; padding: 30px 14px !important; }
    .auth-hero-title { font-size: 26px !important; }
    .auth-hero-sub   { font-size: 13px !important; }
    .auth-card { padding: 24px 16px !important; }

    /* Typography */
    h1 { font-size: 20px !important; line-height: 1.3 !important; }
    h2 { font-size: 17px !important; }
    h3 { font-size: 15px !important; }
    [data-testid="stMain"] p, [data-testid="stMain"] li { font-size: 14px !important; }

    /* KPI cards */
    .kpi-val { font-size: 19px !important; } .kpi-lbl { font-size: 11px !important; }
    .kpi-card { padding: 10px 8px !important; border-radius: 10px !important; }

    /* Inputs */
    [data-testid="stTextInput"] > div > div > input,
    [data-testid="stNumberInput"] > div > div > input,
    [data-testid="stTextArea"] > div > textarea { font-size: 15px !important; padding: 10px 11px !important; }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
        width: 100% !important; font-size: 14px !important; padding: 11px 12px !important;
    }
    [data-testid="stSidebar"] .stButton > button { font-size: 13px !important; padding: 10px 8px !important; }

    /* Tabs */
    [data-testid="stTabs"] [role="tablist"] { flex-wrap: wrap !important; }
    [data-testid="stTabs"] [role="tab"] { font-size: 12px !important; padding: 7px 9px !important; }

    /* Tables */
    table { display: block !important; overflow-x: auto !important;
            font-size: 12px !important; white-space: nowrap !important; }

    /* Misc */
    .wc-temp { font-size: 32px !important; }
    .trip-card, .info-box { padding: 12px !important; border-radius: 10px !important; }
    img { max-width: 100% !important; height: auto !important; }
}

/* ── Small phone  ≤480px ─────────────────────────────────────────────────── */
@media (max-width: 480px) {
    [data-testid="stSidebar"] { width: 220px !important; min-width: 220px !important; max-width: 220px !important; }
    [data-testid="stSidebar"] > div:first-child { width: 220px !important; min-width: 220px !important; }
    .block-container { padding: 54px 0.5rem 1.4rem 0.5rem !important; }
    h1 { font-size: 18px !important; } h2 { font-size: 15px !important; } h3 { font-size: 13px !important; }
    .kpi-val { font-size: 16px !important; } .kpi-card { padding: 8px 6px !important; }
    .wc-temp { font-size: 26px !important; }
    .auth-hero { min-height: 55vh !important; padding: 20px 10px !important; }
    .auth-hero-title { font-size: 20px !important; }
    [data-testid="stTextInput"] > div > div > input,
    [data-testid="stNumberInput"] > div > div > input,
    [data-testid="stTextArea"] > div > textarea { font-size: 14px !important; padding: 8px 10px !important; }
    .stButton > button { font-size: 13px !important; padding: 10px !important; }
    [data-testid="stTabs"] [role="tab"] { font-size: 11px !important; padding: 6px 7px !important; }
    [data-testid="stSidebar"] .stButton > button { font-size: 12px !important; height: 40px !important; }
}


/* ── CARD / WHITE BACKGROUND TEXT ───────────────────────────────────────── */
.kpi-card, .kpi-card * { color: #1e293b !important; }
.trip-card, .trip-card * { color: #475569 !important; }
.trip-card h4 { color: #1b5e20 !important; }
.fc-card * { color: #1e293b !important; }
.info-box .ib-title { color: #1b5e20 !important; }
.info-box .ib-sub   { color: #64748b !important; }
.cred-box * { color: #334155 !important; }
.cred-box .cred-title { color: #1b5e20 !important; }
.itin-box, .itin-box * { color: #1e293b !important; }

/* Metric cards */
.kpi-val { color: #1b5e20 !important; }
.kpi-lbl { color: #64748b !important; }

/* Forecast cards */
.fc-date    { color: #1b5e20 !important; }
.fc-temp-hi { color: #2e7d32 !important; }
.fc-temp-lo { color: #64748b !important; }
.fc-desc    { color: #94a3b8 !important; }

/* Weather card — dark green bg, ALL text stays white */
.weather-card, .weather-card * { color: white !important; }
.weather-card .wc-title  { color: rgba(255,255,255,0.92) !important; }
.weather-card .wc-temp   { color: white !important; }
.weather-card .wc-desc   { color: rgba(255,255,255,0.95) !important; }
.weather-card .wc-detail { color: rgba(255,255,255,0.85) !important; }

/* Section header — green bg, white text */
.sec-hdr, .sec-hdr * { color: white !important; }

/* Auth hero — dark green bg, ALL text white. Uses high-specificity selectors
   to beat the [data-testid="stMarkdownContainer"] span rule (0-0-1-1).
   Specificity here: attribute(1) + class(1) + element(1) = 0-0-2-1 */
[data-testid="stMarkdownContainer"] .auth-hero div,
[data-testid="stMarkdownContainer"] .auth-hero span,
[data-testid="stMarkdownContainer"] .auth-hero p,
[data-testid="stMarkdownContainer"] .auth-hero strong,
[data-testid="stMarkdownContainer"] .auth-hero-title,
[data-testid="stMarkdownContainer"] .auth-hero-sub,
[data-testid="stMarkdownContainer"] .auth-feature-txt {
    color: white !important;
}

/* Auth form panel (white bg, right side) */
.auth-card-title { color: #1b5e20 !important; }
.auth-card-sub   { color: #64748b !important; }

/* Admin badge — dark bg, white text */
.admin-badge { color: white !important; font-size: 12px !important; }

</style>
""", unsafe_allow_html=True)

# ── JavaScript: responsive layout + hamburger sidebar toggle ────────────────
st.components.v1.html("""
<script>
(function () {
  var doc = window.parent.document;
  var win = window.parent;
  var sidebarW = 250;

  /* ─── 1. Inject reinforcing <style> into parent <head> ─────────────────── */
  if (!doc.getElementById('_rsp2')) {
    var st2 = doc.createElement('style');
    st2.id = '_rsp2';
    st2.textContent =
      '@media(max-width:768px){' +
        /* sidebar hidden off-screen by default */
        '[data-testid="stSidebar"]{position:fixed!important;top:0!important;left:0!important;' +
          'height:100vh!important;width:250px!important;min-width:250px!important;' +
          'max-width:250px!important;z-index:99999!important;overflow-y:auto!important;' +
          'transform:translateX(-260px)!important;transition:transform .28s cubic-bezier(.4,0,.2,1)!important;' +
          'visibility:visible!important;display:block!important;opacity:1!important;box-shadow:none!important;}' +
        /* open state */
        '[data-testid="stSidebar"].mob-open{transform:translateX(0)!important;' +
          'box-shadow:6px 0 36px rgba(0,0,0,.28)!important;}' +
        /* main full width */
        'section[data-testid="stMain"],[data-testid="stMain"]{' +
          'margin-left:0!important;width:100vw!important;max-width:100vw!important;' +
          'flex:1 1 100%!important;min-width:0!important;}' +
        /* stack columns */
        '[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;}' +
        '[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{' +
          'flex:0 0 100%!important;width:100%!important;max-width:100%!important;min-width:0!important;}' +
        /* keep auth columns 50/50 */
        '[data-testid="stHorizontalBlock"]:has(.auth-hero)>[data-testid="stColumn"]{' +
          'flex:0 0 50%!important;width:50%!important;max-width:50%!important;}' +
      '}' +
      '@media(max-width:480px){' +
        '[data-testid="stSidebar"]{width:220px!important;min-width:220px!important;max-width:220px!important;}' +
      '}';
    doc.head.appendChild(st2);
  }

  /* ─── 2. Hamburger + overlay setup ─────────────────────────────────────── */
  var isOpen = false;

  function getSidebar() { return doc.querySelector('[data-testid="stSidebar"]'); }
  function getMain()    { return doc.querySelector('section[data-testid="stMain"]'); }

  function openSidebar() {
    var sb = getSidebar(); if (!sb) return;
    sb.classList.add('mob-open');
    var ovl = doc.getElementById('_mob_overlay');
    if (ovl) ovl.style.display = 'block';
    var btn = doc.getElementById('_mob_ham');
    if (btn) btn.innerHTML = '&#10005;';
    isOpen = true;
  }

  function closeSidebar() {
    var sb = getSidebar(); if (!sb) return;
    sb.classList.remove('mob-open');
    var ovl = doc.getElementById('_mob_overlay');
    if (ovl) ovl.style.display = 'none';
    var btn = doc.getElementById('_mob_ham');
    if (btn) btn.innerHTML = '&#9776;';
    isOpen = false;
  }

  function ensureControls() {
    var W = win.innerWidth;
    var sb = getSidebar();

    /* Desktop / tablet: remove mobile controls */
    if (W > 768) {
      var btn = doc.getElementById('_mob_ham');
      var ovl = doc.getElementById('_mob_overlay');
      if (btn) btn.style.display = 'none';
      if (ovl) { ovl.style.display = 'none'; closeSidebar(); }
      return;
    }

    /* Mobile: create hamburger if missing */
    if (!doc.getElementById('_mob_ham')) {
      /* overlay */
      var overlay = doc.createElement('div');
      overlay.id = '_mob_overlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);' +
        'z-index:99998;display:none;backdrop-filter:blur(1px);';
      overlay.addEventListener('click', closeSidebar);
      doc.body.appendChild(overlay);

      /* button */
      var hamburger = doc.createElement('button');
      hamburger.id = '_mob_ham';
      hamburger.innerHTML = '&#9776;';
      hamburger.style.cssText =
        'position:fixed;top:10px;left:10px;z-index:100002;width:44px;height:44px;' +
        'border-radius:10px;background:#1b5e20;border:none;color:white;font-size:22px;' +
        'cursor:pointer;display:flex;align-items:center;justify-content:center;' +
        'box-shadow:0 3px 14px rgba(0,0,0,.32);transition:background .2s;';
      hamburger.addEventListener('click', function () {
        isOpen ? closeSidebar() : openSidebar();
      });
      doc.body.appendChild(hamburger);
    } else {
      /* show existing button (might have been hidden on resize) */
      doc.getElementById('_mob_ham').style.display = 'flex';
      /* only show if sidebar exists (logged-in pages) */
      if (!sb) doc.getElementById('_mob_ham').style.display = 'none';
    }
  }

  /* ─── 3. Fix main-content width on mobile ───────────────────────────────── */
  function fixLayout() {
    var W   = win.innerWidth;
    var main = getMain();
    if (!main) return;

    if (W <= 768) {
      main.style.setProperty('margin-left', '0',       'important');
      main.style.setProperty('width',       '100vw',   'important');
      main.style.setProperty('max-width',   '100vw',   'important');
      main.style.setProperty('flex',        '1 1 100%','important');
      /* stack app columns but skip auth columns */
      doc.querySelectorAll('[data-testid="stHorizontalBlock"]').forEach(function (blk) {
        if (blk.querySelector('.auth-hero')) return;   /* keep auth 50/50 */
        blk.style.setProperty('flex-wrap', 'wrap', 'important');
        blk.querySelectorAll('[data-testid="stColumn"]').forEach(function (col) {
          col.style.setProperty('flex',      '0 0 100%', 'important');
          col.style.setProperty('width',     '100%',     'important');
          col.style.setProperty('max-width', '100%',     'important');
        });
      });
    } else {
      /* restore desktop/tablet layout */
      ['margin-left','width','max-width','flex'].forEach(function (p) {
        main.style.removeProperty(p);
      });
      doc.querySelectorAll('[data-testid="stHorizontalBlock"]').forEach(function (blk) {
        blk.style.removeProperty('flex-wrap');
        blk.querySelectorAll('[data-testid="stColumn"]').forEach(function (col) {
          ['flex','width','max-width'].forEach(function (p) { col.style.removeProperty(p); });
        });
      });
    }
    ensureControls();
  }

  /* ─── 4. Run now + after Streamlit renders ──────────────────────────────── */
  fixLayout();
  win.addEventListener('resize', fixLayout);
  [300, 800, 1800, 4000].forEach(function (t) { setTimeout(fixLayout, t); });
})();
</script>
""", height=0)

# ════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════════════════════════════
for k,v in {"logged_in":False,"username":"","current_itinerary":None,
            "packing_list":None,"budget_tips":None,"surprise":None,
            "phrases":None,"page":"dashboard",
            "places_hotels":None,"places_restaurants":None,
            "places_attractions":None,"places_dest":"",
            "profile_photo_cache": None}.items():
    if k not in st.session_state: st.session_state[k]=v

# ════════════════════════════════════════════════════════════════════════════
# EMAIL VERIFICATION HANDLER  — triggered by ?verify=<token> link in email
# ════════════════════════════════════════════════════════════════════════════
_verify_token = st.query_params.get("verify", "")
if _verify_token and not st.session_state.logged_in:
    _vconn = get_db(); _vcur = _vconn.cursor(dictionary=True)
    _vcur.execute(
        "SELECT username, full_name FROM users WHERE verify_token=%s AND verified=0",
        (_verify_token,)
    )
    _vrow = _vcur.fetchone()
    if _vrow:
        _vcur.execute(
            "UPDATE users SET verified=1, verify_token=NULL WHERE username=%s",
            (_vrow["username"],)
        )
        _vconn.commit()
        _vcur.close(); _vconn.close()
        st.query_params.clear()
        st.success(
            f"Email verified successfully! Welcome, **{_vrow['full_name']}**. "
            f"You can now sign in below."
        )
    else:
        _vcur.close(); _vconn.close()
        st.query_params.clear()
        st.error("This verification link is invalid or has already been used.")

# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# LOGIN / REGISTER  (split-screen layout)
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    # Route: ?portal=admin  →  Admin login/register page
    #        (no param)     →  User login/register page
    is_admin_portal = st.query_params.get("portal", "") == "admin"

    if is_admin_portal:
        # ════════════════════════════════════════════════════════════════
        # ADMIN LOGIN / REGISTER PAGE
        # Direct URL:  http://localhost:8501/?portal=admin
        # ════════════════════════════════════════════════════════════════
        hero_col, form_col = st.columns([1, 1], gap="small")

        with hero_col:
            st.markdown("""
            <div class="auth-hero" style="
                background:linear-gradient(145deg,#0a1628 0%,#0f2d4e 50%,#1a4a6b 100%);
                min-height:92vh;border-radius:0">
                <div class="auth-hero-title" style="color:white!important">Admin<br>Dashboard</div>
                <div class="auth-hero-sub" style="color:rgba(255,255,255,0.82)!important">
                    Secure access for administrators.<br>Manage users, trips and system settings.
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot" style="background:rgba(255,255,255,0.6)"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">Full user &amp; admin management</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot" style="background:rgba(255,255,255,0.6)"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">System-wide analytics</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot" style="background:rgba(255,255,255,0.6)"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">All itineraries &amp; expenses</span>
                </div>
                <div style="margin-top:48px;padding:16px 20px;background:rgba(255,255,255,0.08);
                     border-radius:12px;border:1px solid rgba(255,255,255,0.15)">
                    <div style="font-size:13px;color:rgba(255,255,255,0.5)!important;
                         text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
                         Admin Portal URL</div>
                    <div style="font-size:14px;color:rgba(255,255,255,0.85)!important;
                         font-family:monospace">localhost:8501/?portal=admin</div>
                </div>
            </div>""", unsafe_allow_html=True)

        with form_col:
            st.markdown('<div style="height:40px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="admin-badge">ADMIN PORTAL</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-card-title">Administrator Access</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-card-sub">Restricted — authorised personnel only.</div>',
                        unsafe_allow_html=True)
            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

            atab_login, atab_reg = st.tabs(["Sign In", "Register Admin"])

            with atab_login:
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                with st.form("admin_lf"):
                    adm_u = st.text_input("Admin Username", placeholder="admin")
                    adm_p = st.text_input("Password", type="password",
                                          placeholder="Enter admin password")
                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                    adm_btn = st.form_submit_button("Sign In to Admin Dashboard",
                                                    use_container_width=True)
                if adm_btn:
                    if not adm_u or not adm_p:
                        st.error("Please enter both username and password.")
                    elif authenticate_admin(adm_u.strip(), adm_p):
                        st.session_state.logged_in = True
                        st.session_state.username  = adm_u.strip()
                        st.session_state.page      = "admin"   # go to admin dashboard
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.error("Invalid admin credentials. Try admin / Admin@1234")
                st.markdown("""
                <div class="cred-box">
                    <span class="cred-title">Default Admin Credentials</span>
                    <span class="cred-info">
                        <strong>admin</strong> &nbsp;/&nbsp; <strong>Admin@1234</strong>
                    </span>
                </div>""", unsafe_allow_html=True)

            with atab_reg:
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                with st.form("admin_rf", clear_on_submit=True):
                    arn  = st.text_input("Full Name",        placeholder="Administrator name")
                    aru  = st.text_input("Username",         placeholder="3+ chars, letters/numbers/_")
                    are  = st.text_input("Email (optional)", placeholder="admin@company.com")
                    arp  = st.text_input("Password", type="password",
                                         placeholder="8+ chars, uppercase, number, symbol")
                    arp2 = st.text_input("Confirm Password", type="password",
                                         placeholder="Repeat password")
                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                    arbtn = st.form_submit_button("Create Admin Account", use_container_width=True)
                if arp:
                    strength = pw_strength(arp)
                    bar_w = {"Very Weak":20,"Weak":40,"Fair":60,"Strong":80,"Very Strong":100}.get(strength,0)
                    bar_c = {"Very Weak":"#ef4444","Weak":"#f97316","Fair":"#eab308",
                             "Strong":"#22c55e","Very Strong":"#16a34a"}.get(strength,"#ccc")
                    st.markdown(f"""
                    <div style="margin-top:8px">
                        <div style="background:#e2e8f0;border-radius:99px;height:6px;overflow:hidden">
                            <div style="background:{bar_c};width:{bar_w}%;height:100%;border-radius:99px"></div>
                        </div>
                        <p style="font-size:13px;color:{bar_c}!important;font-weight:700;margin-top:4px">
                            Strength: {strength}</p>
                    </div>""", unsafe_allow_html=True)
                if arbtn:
                    if arp != arp2:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_admin(aru, arp, arn, are)
                        (st.success if ok else st.error)(msg)

            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            if st.button("Back to User Login", use_container_width=False):
                st.query_params.clear(); st.rerun()

    else:
        # ════════════════════════════════════════════════════════════════
        # USER LOGIN / REGISTER PAGE  (no admin link — completely separate)
        # ════════════════════════════════════════════════════════════════
        hero_col, form_col = st.columns([1, 1], gap="small")

        with hero_col:
            st.markdown("""
            <div class="auth-hero" style="min-height:92vh;border-radius:0">
                <div class="auth-hero-title" style="color:white!important">
                    AI Travel<br>Planner
                </div>
                <div class="auth-hero-sub" style="color:rgba(255,255,255,0.82)!important">
                    Your intelligent AI-powered travel companion.<br>Plan smarter. Travel better.
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">
                        AI day-by-day itineraries in seconds</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">
                        Live weather &amp; 5-day forecasts</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">
                        Hotel &amp; restaurant suggestions</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">
                        Expense tracker &amp; PDF export</span>
                </div>
                <div class="auth-feature">
                    <div class="auth-feature-dot"></div>
                    <span class="auth-feature-txt" style="color:rgba(255,255,255,0.88)!important">
                        Multi-currency budget planner</span>
                </div>
            </div>""", unsafe_allow_html=True)

        with form_col:
            st.markdown('<div style="height:40px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-card-title">Welcome back</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-card-sub">Sign in to your account or create a new one.</div>',
                        unsafe_allow_html=True)
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

            ltab, rtab = st.tabs(["Sign In", "Create Account"])

            with ltab:
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                with st.form("lf"):
                    uname = st.text_input("Username or Email",
                                          placeholder="Enter your username or email")
                    passw = st.text_input("Password", type="password",
                                          placeholder="Enter your password")
                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                    lbtn  = st.form_submit_button("Sign In", use_container_width=True)
                if lbtn:
                    if not uname or not passw:
                        st.error("Please enter your username/email and password.")
                    else:
                        ok, actual_username = authenticate(uname.strip(), passw)
                        if ok is True:
                            st.session_state.logged_in = True
                            st.session_state.username  = actual_username
                            st.rerun()
                        elif ok == "unverified":
                            st.warning(
                                "Your email address has not been verified yet. "
                                "Please check your inbox and click the verification link."
                            )
                        else:
                            st.error("Incorrect username/email or password.")

            with rtab:
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                with st.form("rf", clear_on_submit=True):
                    rn  = st.text_input("Full Name",   placeholder="Your full name")
                    ru  = st.text_input("Username",    placeholder="3+ chars, letters/numbers/_")
                    rem = st.text_input("Email",       placeholder="your@email.com")
                    rp  = st.text_input("Password",    type="password",
                                        placeholder="Min 6 chars + 1 number")
                    rp2 = st.text_input("Confirm Password", type="password",
                                        placeholder="Repeat your password")
                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                    rbtn = st.form_submit_button("Create Account", use_container_width=True)
                if rp:
                    strength = pw_strength(rp)
                    bar_w = {"Very Weak":20,"Weak":40,"Fair":60,"Strong":80,"Very Strong":100}.get(strength,0)
                    bar_c = {"Very Weak":"#ef4444","Weak":"#f97316","Fair":"#eab308",
                             "Strong":"#22c55e","Very Strong":"#16a34a"}.get(strength,"#ccc")
                    st.markdown(f"""
                    <div style="margin-top:8px">
                        <div style="background:#e2e8f0;border-radius:99px;height:6px;overflow:hidden">
                            <div style="background:{bar_c};width:{bar_w}%;height:100%;
                                 border-radius:99px;transition:width 0.3s"></div>
                        </div>
                        <p style="font-size:13px;color:{bar_c}!important;font-weight:700;margin-top:4px">
                            Password strength: {strength}</p>
                    </div>""", unsafe_allow_html=True)
                if rbtn:
                    if rp != rp2:
                        st.error("Passwords do not match.")
                    else:
                        ok, msg = register_user(ru, rp, rn, rem)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ════════════════════════════════════════════════════════════════════════════
uinfo = get_user_info(st.session_state.username)

with st.sidebar:
    # Brand header with profile photo
    role = uinfo.get("role","user")
    _photo_bytes = get_profile_photo(st.session_state.username)
    if _photo_bytes:
        _b64 = base64.b64encode(_photo_bytes).decode()
        _avatar_html = f'<img src="data:image/jpeg;base64,{_b64}" style="width:64px;height:64px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,0.5);margin-bottom:10px;">'
    else:
        _initials = "".join(w[0].upper() for w in uinfo.get("full_name", st.session_state.username).split()[:2]) or "U"
        _avatar_html = f'<div style="width:64px;height:64px;border-radius:50%;background:rgba(255,255,255,0.25);border:3px solid rgba(255,255,255,0.5);display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:900;color:#ffffff;margin:0 auto 10px auto;">{_initials}</div>'
    st.markdown(f"""
    <div style="padding:22px 12px 14px 12px; text-align:center;
         background:linear-gradient(135deg,#1b5e20,#2e7d32);
         border-radius:0 0 16px 16px; margin-bottom:14px;">
        {_avatar_html}
        <div style="font-size:18px;font-weight:900;color:#ffffff;letter-spacing:-0.3px;">
            {uinfo.get('name', st.session_state.username)}</div>
        <div style="font-size:11px;color:rgba(255,255,255,0.75);margin-top:3px;
             text-transform:uppercase;letter-spacing:1.2px;">{role}</div>
    </div>
    """, unsafe_allow_html=True)

    nav_items = [
        ("Dashboard",       "dashboard"),
        ("Plan a Trip",     "planner"),
        ("My Itineraries",  "saved"),
        ("Expense Tracker", "expenses"),
        ("Analytics",       "analytics"),
        ("Weather",         "weather"),
        ("Places",          "places"),
        ("AI Tools",        "tools"),
        ("Settings",        "settings"),
    ]
    if role == "admin":
        nav_items.append(("Admin Dashboard", "admin"))
    for label, key in nav_items:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.page=key; st.rerun()

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:1px;background:#e8f5e9;margin:0 14px 10px 14px;"></div>',
                unsafe_allow_html=True)

    if st.button("Sign Out", key="nav_logout", use_container_width=True):
        for k in ["logged_in","username","current_itinerary","packing_list","budget_tips","surprise","phrases"]:
            st.session_state[k]=False if k=="logged_in" else ("" if k=="username" else None)
        st.rerun()

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

page = st.session_state.page
user_currency = uinfo.get("pref_currency", "USD")

# ════════════════════════════════════════════════════════════════════════════
# HELPER: KPI ROW
# ════════════════════════════════════════════════════════════════════════════
def kpi_row(items):
    cols = st.columns(len(items), gap="medium")
    for col,(icon,val,lbl) in zip(cols, items):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <span class="kpi-icon">{icon}</span>
                <div class="kpi-val">{val}</div>
                <div class="kpi-lbl">{lbl}</div>
            </div>""", unsafe_allow_html=True)

def sec(label):
    st.markdown(f'<div class="sec-hdr">{label}</div>', unsafe_allow_html=True)

def spacer(px=20):
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if page == "dashboard":
    st.markdown(f"## Welcome back, {uinfo.get('name', st.session_state.username)}!")
    st.markdown("Your travel overview — everything at a glance.")
    spacer(24)

    my_trips     = get_user_itineraries(st.session_state.username)
    user_exp     = get_user_expenses(st.session_state.username)
    total_spent  = sum(e.get("amount",0) for e in user_exp)
    total_budget = sum(r.get("budget",0) for r in my_trips)
    total_days   = sum(r.get("days",0) for r in my_trips)

    kpi_row([
        ("Trips",   len(my_trips),           "Trips Planned"),
        ("Budget",  f"${total_budget:,.0f}", "Total Budget"),
        ("Spent",   f"${total_spent:,.0f}",  "Total Spent"),
        ("Days",    total_days,              "Days Planned"),
    ])
    spacer(28)

    cl, cr = st.columns([3,2], gap="large")
    with cl:
        sec("Recent Trips")
        if my_trips:
            for rec in my_trips[-5:][::-1]:
                star_marker = "Starred · " if rec.get("starred") else ""
                st.markdown(f"""
                <div class="trip-card">
                    <h4>{rec.get('destination','Unknown')}</h4>
                    <p><strong>{rec.get('days','?')} days</strong>
                       &nbsp;·&nbsp; <strong>${rec.get('budget',0):,.0f}</strong>
                       &nbsp;·&nbsp; {rec.get('travel_type','')}</p>
                    <p style="color:#94a3b8!important; font-size:14px!important;">
                        {star_marker}Saved: {rec.get('saved_on','?')}
                    </p>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div class="info-box">
                <div class="ib-title">No trips yet!</div>
                <div class="ib-sub">Head to <strong>Plan a Trip</strong> to create your first adventure.</div>
            </div>""", unsafe_allow_html=True)

    with cr:
        sec("Budget Overview")
        if my_trips:
            st.plotly_chart(pie_chart(total_budget), use_container_width=True, key="dash_pie")
        else:
            st.info("Plan a trip to see your budget breakdown.")

# ════════════════════════════════════════════════════════════════════════════
# PLAN A TRIP
# ════════════════════════════════════════════════════════════════════════════
elif page == "planner":
    st.markdown("## Plan a New Trip")
    st.markdown("Fill in your details and let AI craft your perfect day-by-day itinerary.")
    spacer(20)

    col_form, col_result = st.columns([1,1], gap="large")

    with col_form:
        sec("Trip Details")
        with st.form("itinerary_form"):
            destination = st.text_input("Destination", placeholder="e.g. Tokyo, Japan")
            c1,c2 = st.columns(2)
            with c1:
                days       = st.number_input("Days", min_value=1, max_value=60, value=5)
                start_date = st.date_input("Start Date", value=date.today())
            with c2:
                budget    = st.number_input(f"Budget ({user_currency})", min_value=100.0, value=1500.0, step=50.0)
                travelers = st.number_input("Travelers", min_value=1, max_value=20, value=1)
            travel_type = st.selectbox("Travel Style",[
                "Budget Backpacker","Mid-Range Explorer","Luxury Traveler",
                "Family Trip","Solo Adventure","Romantic Getaway",
                "Business Trip","Adventure Seeker"])
            activities = st.text_area("Interests", placeholder="e.g. Museums, Street Food, Hiking, Nightlife", height=90)
            notes      = st.text_area("Special Notes (optional)", placeholder="e.g. Vegetarian, wheelchair accessible", height=68)
            spacer(4)

            with st.expander("Advanced Options — click to expand"):
                # ── GROUP & TRAVELER PROFILE ─────────────────────────────────
                st.markdown("**Group & Traveler Profile**")
                g1, g2 = st.columns(2)
                with g1:
                    group_type = st.selectbox("Group Type",
                        ["Solo","Couple","Family with kids","Friends group","Corporate / Business"])
                    eco = st.checkbox("Eco-friendly / sustainable travel")
                with g2:
                    kids_ages = st.text_input("Kids' ages (if applicable)",
                        placeholder="e.g. 4, 7, 12")
                    pet = st.checkbox("Pet-friendly trip")
                trip_theme = st.selectbox("Trip Theme",
                    ["General","Cultural Immersion","Culinary Journey",
                     "Photography Tour","Adventure & Sports","Wellness & Spa",
                     "Shopping & Fashion","Nightlife & Entertainment",
                     "History & Architecture","Nature & Wildlife"])
                st.markdown("---")

                # ── ACCOMMODATION & TRANSPORT ────────────────────────────────
                st.markdown("**Accommodation & Transport**")
                a1, a2 = st.columns(2)
                with a1:
                    accommodation = st.selectbox("Accommodation Type",
                        ["Any","Hotel","Hostel / Dorm","Airbnb / Apartment",
                         "Boutique Hotel","Resort","Camping / Glamping"])
                    meal_pref = st.selectbox("Meal Preference",
                        ["No preference","Vegetarian","Vegan","Halal",
                         "Kosher","Gluten-free","Local cuisine only"])
                with a2:
                    transport = st.selectbox("Primary Transport",
                        ["Any","Flight","Train / Rail","Road Trip",
                         "Public Transit","Cruise","Cycling / Walking"])
                    pace = st.selectbox("Trip Pace",
                        ["Relaxed","Moderate","Action-packed"])
                fitness = st.select_slider("Fitness / Activity Level",
                    options=["Low (easy walks only)","Moderate",
                             "Active (hikes & sports)","High (extreme activities)"],
                    value="Moderate")
                st.markdown("---")

                # ── DAILY SCHEDULE PREFERENCES ───────────────────────────────
                st.markdown("**Daily Schedule Preferences**")
                d1, d2 = st.columns(2)
                with d1:
                    day_start = st.selectbox("Day Start Time",
                        ["Early bird (6 am)","Standard (8 am)","Late riser (10 am+)"])
                    nightlife = st.checkbox("Include nightlife & evening entertainment")
                with d2:
                    restaurant_meals = st.selectbox("Restaurant meals per day",
                        [1, 2, 3], index=1)
                    off_peak = st.checkbox("Prefer off-peak timings to avoid crowds")
                st.markdown("---")

                # ── MUST-VISIT & AVOID ───────────────────────────────────────
                st.markdown("**Places & Preferences**")
                mv1, mv2 = st.columns(2)
                with mv1:
                    must_visit = st.text_input("Must-Visit Spots",
                        placeholder="e.g. Eiffel Tower, local night market")
                with mv2:
                    avoid = st.text_input("Places / Things to Avoid",
                        placeholder="e.g. tourist traps, nightclubs, crowds")
                st.markdown("---")

                # ── BUDGET CUSTOMIZATION ─────────────────────────────────────
                st.markdown("**Budget Customization**")
                b1, b2 = st.columns(2)
                with b1:
                    budget_priority = st.selectbox("Budget Priority",
                        ["Balanced","Prioritize accommodation",
                         "Prioritize food & dining","Prioritize activities & experiences",
                         "Prioritize transport & comfort"])
                with b2:
                    currency = st.selectbox("Display costs in", CURRENCY_LIST,
                        index=CURRENCY_LIST.index(user_currency) if user_currency in CURRENCY_LIST else 0)
                st.markdown("---")

                # ── EXTRA CONTENT SECTIONS ───────────────────────────────────
                st.markdown("**Extra Sections to Include in Itinerary**")
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    lang_tips      = st.checkbox("Local phrases")
                    emergency_tips = st.checkbox("Safety & emergency contacts")
                    photo_spots    = st.checkbox("Best photography spots")
                with ec2:
                    visa_info   = st.checkbox("Visa & entry requirements")
                    health_tips = st.checkbox("Health & vaccination tips")
                    day_trips   = st.checkbox("Nearby day-trip suggestions")
                with ec3:
                    local_events = st.checkbox("Local festivals & events")
                spacer(4)

            spacer(4)
            gen_btn = st.form_submit_button("Generate My Itinerary", use_container_width=True)

        spacer(14)
        sec("Quick AI Tools")
        ta, tb = st.columns(2)
        with ta:
            if st.button("Packing List", use_container_width=True):
                r=st.session_state.current_itinerary
                if r:
                    with st.spinner("Generating packing list…"):
                        st.session_state.packing_list=generate_packing_list(r["destination"],r["days"],r["travel_type"],r["activities"])
                else: st.warning("Generate an itinerary first.")
        with tb:
            if st.button("Budget Tips", use_container_width=True):
                r=st.session_state.current_itinerary
                if r:
                    with st.spinner("Generating tips…"):
                        st.session_state.budget_tips=generate_budget_tips(r["destination"],r["budget"],r["travel_type"])
                else: st.warning("Generate an itinerary first.")

    if gen_btn:
        if not destination.strip():
            st.warning("Please enter a destination.")
        else:
            with st.spinner("AI is crafting your personalised itinerary…"):
                text=generate_itinerary_ai(
                    destination,days,budget,travel_type,activities,str(start_date),
                    accommodation=accommodation,transport=transport,
                    meal_pref=meal_pref,pace=pace,fitness=fitness,
                    must_visit=must_visit,avoid=avoid,
                    lang_tips=lang_tips,visa_info=visa_info,travelers=travelers,
                    group_type=group_type,kids_ages=kids_ages,eco=eco,pet=pet,
                    day_start=day_start,restaurant_meals=restaurant_meals,
                    nightlife=nightlife,off_peak=off_peak,
                    budget_priority=budget_priority,currency=currency,
                    emergency_tips=emergency_tips,health_tips=health_tips,
                    photo_spots=photo_spots,day_trips=day_trips,
                    local_events=local_events,trip_theme=trip_theme)
                rec={"id":str(uuid.uuid4()),"destination":destination,"days":days,
                     "start_date":str(start_date),"budget":budget,"travelers":travelers,
                     "travel_type":travel_type,"activities":activities,"notes":notes,
                     "accommodation":accommodation,"transport":transport,
                     "meal_pref":meal_pref,"pace":pace,"fitness":fitness,
                     "must_visit":must_visit,"avoid":avoid,
                     "group_type":group_type,"kids_ages":kids_ages,"eco":eco,"pet":pet,
                     "trip_theme":trip_theme,"day_start":day_start,
                     "restaurant_meals":restaurant_meals,"nightlife":nightlife,
                     "off_peak":off_peak,"budget_priority":budget_priority,"currency":currency,
                     "itinerary":text,"packing_list":None,"saved_on":str(date.today()),
                     "user":st.session_state.username,"starred":False}
                st.session_state.current_itinerary=rec
                save_itinerary_to_file(rec)
            st.success("Itinerary generated and saved!")

    with col_result:
        rec = st.session_state.current_itinerary
        if rec:
            st.markdown(f"### {rec['destination']}")
            _rc = rec.get("currency", user_currency)
            st.markdown(f"**{rec['days']} days** &nbsp;·&nbsp; **{csym(_rc)}{rec['budget']:,.0f} {_rc}** &nbsp;·&nbsp; **{rec['travel_type']}** &nbsp;·&nbsp; from `{rec.get('start_date','')}`")
            spacer(12)

            # Weather
            w=get_weather(rec["destination"].split(",")[0])
            if w:
                st.markdown(f"""
                <div class="weather-card">
                    <div class="wc-title">Current Weather — {rec["destination"].split(",")[0].strip()}</div>
                    <div class="wc-temp">{w['temp']}°C</div>
                    <div class="wc-desc">{w['desc']} &nbsp;·&nbsp; Feels like {w['feels']}°C</div>
                    <div class="wc-detail">Humidity {w['humidity']}% &nbsp;&nbsp;·&nbsp;&nbsp; Wind {w['wind']} km/h</div>
                </div>""", unsafe_allow_html=True)
                spacer(14)

            # Budget chart
            st.plotly_chart(pie_chart(rec["budget"]), use_container_width=True, key="plan_pie")

            # Itinerary
            with st.expander("Full Itinerary", expanded=True):
                st.markdown(f'<div class="itin-box">{rec["itinerary"]}</div>', unsafe_allow_html=True)

            if st.session_state.packing_list:
                with st.expander("Packing List"):
                    st.markdown(st.session_state.packing_list)
            if st.session_state.budget_tips:
                with st.expander("Budget Tips"):
                    st.markdown(st.session_state.budget_tips)

            spacer(8)
            sec("Actions")
            a1,a2,a3 = st.columns(3)
            with a1:
                pdf=build_pdf(rec)
                safe=rec["destination"].replace(" ","_").replace(",","")
                st.download_button("Download PDF",pdf,f"Itinerary_{safe}.pdf","application/pdf",use_container_width=True)
            with a2:
                starred=rec.get("starred",False)
                if st.button("Starred" if starred else "Star Trip",use_container_width=True):
                    rec["starred"]=not starred; st.session_state.current_itinerary=rec
                    save_itinerary_to_file(rec); st.rerun()
            with a3:
                if st.button("Email PDF",use_container_width=True):
                    st.session_state.page="settings"; st.rerun()
        else:
            st.markdown("""
            <div class="info-box" style="margin-top:12px">
                <div class="ib-title">Ready to plan?</div>
                <div class="ib-sub">
                    Fill in the form on the left and click<br>
                    <strong>Generate My Itinerary</strong>
                </div>
            </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# MY ITINERARIES
# ════════════════════════════════════════════════════════════════════════════
elif page == "saved":
    st.markdown("## My Saved Itineraries")
    my_trips=get_user_itineraries(st.session_state.username)

    if not my_trips:
        st.markdown("""<div class="info-box" style="max-width:600px;margin:30px auto">
            <div class="ib-title">No itineraries yet</div>
            <div class="ib-sub">Go to <strong>Plan a Trip</strong> to create your first adventure!</div>
        </div>""", unsafe_allow_html=True)
    else:
        fc1,fc2,fc3 = st.columns([2.5,1.8,1.2], gap="medium")
        with fc1: search=st.text_input("Search destination","")
        with fc2: sort_by=st.selectbox("Sort by",["Newest First","Oldest First","Budget High","Budget Low","Most Days"])
        with fc3:
            spacer(28)
            star_filter=st.checkbox("Starred only",False)

        filtered=[r for r in my_trips if search.lower() in r.get("destination","").lower()]
        if star_filter: filtered=[r for r in filtered if r.get("starred")]
        if   sort_by=="Newest First":  filtered=filtered[::-1]
        elif sort_by=="Budget High":   filtered=sorted(filtered,key=lambda x:x.get("budget",0),reverse=True)
        elif sort_by=="Budget Low":    filtered=sorted(filtered,key=lambda x:x.get("budget",0))
        elif sort_by=="Most Days":     filtered=sorted(filtered,key=lambda x:x.get("days",0),reverse=True)

        spacer(8)
        st.markdown(f'<p style="font-size:16px;font-weight:700;color:#475569;">Showing <span style="color:#1b5e20">{len(filtered)}</span> trip(s)</p>', unsafe_allow_html=True)
        spacer(4)

        for rec in filtered:
            star_prefix = "Starred · " if rec.get("starred") else ""
            title=f"{star_prefix}{rec.get('destination','?')}  —  {rec.get('days','?')} days  ·  ${rec.get('budget',0):,.0f}  ·  {rec.get('saved_on','?')}"
            with st.expander(title):
                ic,ac=st.columns([4,1], gap="large")
                with ic:
                    def _tag(label, val, skip=""):
                        return f"<p><strong>{label}:</strong> {val}</p>" if val and str(val) not in ("",skip,"False") else ""
                    flags = " &nbsp;·&nbsp; ".join(filter(None,[
                        "Eco-friendly" if rec.get("eco") else "",
                        "Pet-friendly" if rec.get("pet") else "",
                        "Nightlife" if rec.get("nightlife") else "",
                        "Off-peak" if rec.get("off_peak") else "",
                    ]))
                    adv_extras = "".join([
                        _tag("Group",   rec.get("group_type")),
                        _tag("Kids ages", rec.get("kids_ages")),
                        _tag("Theme",     rec.get("trip_theme"),    "General"),
                        _tag("Stay",      rec.get("accommodation"), "Any"),
                        _tag("Transport", rec.get("transport"),     "Any"),
                        _tag("Meals",     rec.get("meal_pref"),    "No preference"),
                        _tag("Pace",      rec.get("pace")),
                        _tag("Fitness",   rec.get("fitness")),
                        _tag("Day start", rec.get("day_start")),
                        _tag("Currency",  rec.get("currency"),      "USD"),
                        _tag("Budget priority", rec.get("budget_priority"), "Balanced"),
                        _tag("Must-visit",rec.get("must_visit")),
                        _tag("Avoid",     rec.get("avoid")),
                        f"<p>{flags}</p>" if flags else "",
                    ])
                    st.markdown(f"""
                    <div style="background:#f9fdf9;border-radius:12px;padding:16px 20px;margin-bottom:14px;border:1.5px solid #e8f5e9">
                        <p><strong>Style:</strong> {rec.get('travel_type','—')} &nbsp;·&nbsp; <strong>Travelers:</strong> {rec.get('travelers',1)}</p>
                        <p><strong>Activities:</strong> {rec.get('activities','—')}</p>
                        {adv_extras}
                        {"<p><strong>Notes:</strong> " + rec.get('notes','') + "</p>" if rec.get('notes') else ""}
                    </div>""", unsafe_allow_html=True)
                    st.markdown(f'<div class="itin-box">{rec.get("itinerary","")}</div>', unsafe_allow_html=True)
                with ac:
                    spacer(8)
                    exp=get_trip_expenses(rec.get("id",""))
                    pdf=build_pdf(rec,exp)
                    safe=rec.get("destination","Trip").replace(" ","_").replace(",","")
                    st.download_button("PDF",pdf,f"Itinerary_{safe}.pdf","application/pdf",use_container_width=True,key=f"dl_{rec.get('id')}")
                    spacer(6)
                    if st.button("Unstar" if rec.get("starred") else "Star",key=f"star_{rec.get('id')}",use_container_width=True):
                        rec["starred"]=not rec.get("starred",False); save_itinerary_to_file(rec); st.rerun()
                    spacer(6)
                    if st.button("Reload",key=f"rel_{rec.get('id')}",use_container_width=True):
                        st.session_state.current_itinerary=rec; st.session_state.page="planner"; st.rerun()
                    spacer(6)
                    if st.button("Delete",key=f"del_{rec.get('id')}",use_container_width=True):
                        delete_itinerary(rec.get("id"),st.session_state.username); st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# EXPENSE TRACKER
# ════════════════════════════════════════════════════════════════════════════
elif page == "expenses":
    st.markdown("## Expense Tracker")
    st.markdown("Log your actual spending and track it against your planned budget.")
    my_trips=get_user_itineraries(st.session_state.username)

    if not my_trips:
        st.info("Plan a trip first, then come back to log expenses.")
    else:
        spacer(8)
        tlabels={r["id"]:f"{r.get('destination','?')}  ({r.get('start_date','?')})" for r in my_trips}
        sel_id=st.selectbox("Select Trip",list(tlabels.keys()),format_func=lambda x:tlabels[x])
        sel_rec=next((r for r in my_trips if r["id"]==sel_id),{})
        t_budget=sel_rec.get("budget",0); t_exp=get_trip_expenses(sel_id)
        t_spent=sum(e.get("amount",0) for e in t_exp); remain=t_budget-t_spent
        pct=(t_spent/t_budget*100) if t_budget else 0
        _ec = sel_rec.get("currency", user_currency); _es = csym(_ec)

        spacer(16)
        kpi_row([
            ("Budget",  f"{_es}{t_budget:,.2f}","Total Budget"),
            ("Spent",   f"{_es}{t_spent:,.2f}", "Total Spent"),
            ("Left",    f"{_es}{remain:,.2f}",  "Remaining"),
            ("Used",    f"{pct:.1f}%",           "Budget Used"),
        ])
        spacer(18)

        bar_c="#ef4444" if pct>90 else "#f59e0b" if pct>70 else "#22c55e"
        pct_label="Over 90% used — watch your spending!" if pct>90 else f"{pct:.1f}% of budget used"
        st.markdown(f"""
        <div style="background:white;border-radius:14px;padding:18px 22px;
             box-shadow:0 2px 10px rgba(27,94,32,0.08);margin-bottom:20px">
            <div style="font-size:15px;font-weight:700;color:#1b5e20;margin-bottom:10px">{pct_label}</div>
            <div style="background:#e2e8f0;border-radius:99px;height:16px;overflow:hidden">
                <div style="background:{bar_c};width:{min(pct,100):.1f}%;height:100%;border-radius:99px;
                     transition:width 0.5s ease"></div>
            </div>
        </div>""", unsafe_allow_html=True)
        if pct>90: st.warning("You have used over 90% of your budget! Consider adjusting your plans.")

        ca,cb=st.columns([1,1],gap="large")
        with ca:
            sec("Log New Expense")
            with st.form("ef"):
                e_date=st.date_input("Date",value=date.today())
                e_cat=st.selectbox("Category",["Accommodation","Food","Transport","Activities","Shopping","Misc"])
                e_desc=st.text_input("Description",placeholder="e.g. Hotel check-in, Lunch at café")
                e_amt=st.number_input(f"Amount ({rec.get('currency', user_currency)})",min_value=0.01,step=0.01,value=10.00)
                spacer(4)
                if st.form_submit_button("Add Expense",use_container_width=True):
                    save_expense({"id":str(uuid.uuid4()),"itinerary_id":sel_id,
                                  "user":st.session_state.username,"date":str(e_date),
                                  "category":e_cat,"description":e_desc,"amount":e_amt})
                    st.success("Expense logged!"); st.rerun()
        with cb:
            ch=expense_chart(t_exp,t_budget,_ec)
            if ch: st.plotly_chart(ch,use_container_width=True,key="exp_ch")
            else:
                st.markdown("""<div class="info-box">
                    <div class="ib-title">No expenses yet</div>
                    <div class="ib-sub">Log your first expense to see the chart.</div>
                </div>""", unsafe_allow_html=True)

        if t_exp:
            spacer(8)
            sec("Expense Log")
            # Header row
            st.markdown("""
            <div style="display:grid;grid-template-columns:120px 140px 1fr 110px 50px;
                 gap:12px;padding:12px 16px;background:#2e7d32;border-radius:12px;
                 margin-bottom:8px;color:white;font-size:14px;font-weight:700">
                <span style="color:white!important">Date</span>
                <span style="color:white!important">Category</span>
                <span style="color:white!important">Description</span>
                <span style="color:white!important;text-align:right">Amount</span>
                <span></span>
            </div>""", unsafe_allow_html=True)
            for i,e in enumerate(sorted(t_exp,key=lambda x:x.get("date",""),reverse=True)):
                bg="#f9fdf9" if i%2==0 else "white"
                c1,c2,c3,c4,c5=st.columns([1.2,1.4,2.8,1.1,0.5],gap="small")
                with c1: st.markdown(f'<p style="font-size:15px;color:#475569;padding:6px 0">{e.get("date","")}</p>',unsafe_allow_html=True)
                with c2: st.markdown(f'<p style="font-size:15px;color:#475569;padding:6px 0">{e.get("category","")}</p>',unsafe_allow_html=True)
                with c3: st.markdown(f'<p style="font-size:15px;color:#1e293b;padding:6px 0">{e.get("description","")}</p>',unsafe_allow_html=True)
                with c4: st.markdown(f'<p style="font-size:16px;font-weight:700;color:#1b5e20;padding:6px 0;text-align:right">{_es}{e.get("amount",0):.2f}</p>',unsafe_allow_html=True)
                with c5:
                    if st.button("X",key=f"de_{e.get('id')}",help="Delete expense"):
                        delete_expense(e.get("id")); st.rerun()
                st.divider()

# ════════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
elif page == "analytics":
    st.markdown("## Trip Analytics")
    st.markdown("Visual insights into all your travel plans.")
    my_trips=get_user_itineraries(st.session_state.username)

    if not my_trips:
        st.markdown("""<div class="info-box" style="max-width:600px;margin:30px auto">
            <div class="ib-title">No data yet</div>
            <div class="ib-sub">Plan some trips to unlock your analytics dashboard!</div>
        </div>""", unsafe_allow_html=True)
    else:
        total_days=sum(r.get("days",0) for r in my_trips)
        avg_budget=sum(r.get("budget",0) for r in my_trips)/len(my_trips)
        cities=len(set(r.get("destination","").split(",")[0].strip() for r in my_trips))
        spacer(8)
        kpi_row([
            ("Trips",  len(my_trips),                              "Total Trips"),
            ("Days",   total_days,                                 "Total Days"),
            ("Budget", f"{csym(user_currency)}{avg_budget:,.0f}", f"Avg Budget ({user_currency})"),
            ("Cities", cities,                                     "Destinations"),
        ])
        spacer(28)

        ac1,ac2=st.columns(2,gap="large")
        with ac1:
            names=[r.get("destination","")[:18] for r in my_trips]
            budgets=[r.get("budget",0) for r in my_trips]
            _trip_syms=[csym(r.get("currency",user_currency)) for r in my_trips]
            fig=go.Figure(go.Bar(x=names,y=budgets,marker_color="#2e7d32",
                text=[f"{s}{b:,.0f}" for s,b in zip(_trip_syms,budgets)],textposition="outside",textfont=dict(size=14)))
            fig.update_layout(title=dict(text="Budget per Trip",font=dict(size=18,color="#1b5e20")),
                yaxis_title=user_currency,xaxis=dict(tickfont=dict(size=14)),yaxis=dict(tickfont=dict(size=14)),
                height=360,margin=dict(t=55,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,use_container_width=True,key="a_bar")
        with ac2:
            styles={}
            for r in my_trips: styles[r.get("travel_type","Other")]=styles.get(r.get("travel_type","Other"),0)+1
            fig2=go.Figure(go.Pie(labels=list(styles.keys()),values=list(styles.values()),hole=0.42,textfont=dict(size=14)))
            fig2.update_layout(title=dict(text="Travel Style Mix",font=dict(size=18,color="#1b5e20")),
                legend=dict(font=dict(size=14)),height=360,margin=dict(t=55,b=10),
                paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2,use_container_width=True,key="a_style")

        tl=timeline_chart(my_trips)
        if tl: st.plotly_chart(tl,use_container_width=True,key="a_tl")

        fig3=go.Figure(go.Histogram(x=[r.get("days",0) for r in my_trips],nbinsx=10,marker_color="#2e7d32"))
        fig3.update_layout(title=dict(text="Trip Length Distribution",font=dict(size=18,color="#1b5e20")),
            xaxis=dict(title="Days",tickfont=dict(size=14)),yaxis=dict(title="Trips",tickfont=dict(size=14)),
            height=320,margin=dict(t=55,b=10),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig3,use_container_width=True,key="a_hist")

# ════════════════════════════════════════════════════════════════════════════
# WEATHER
# ════════════════════════════════════════════════════════════════════════════
elif page == "weather":
    st.markdown("## Weather Lookup")
    st.markdown("Check live conditions and 5-day forecast for any city worldwide.")
    spacer(16)

    city=st.text_input("Enter city name", placeholder="e.g. Tokyo, Bangkok, Paris, New York")

    if city:
        w=get_weather(city); fc=get_forecast(city)
        if w:
            spacer(8)
            st.markdown(f"""
            <div class="weather-card">
                <div class="wc-title">{city.title()} — Live Conditions</div>
                <div class="wc-temp">{w['temp']}°C</div>
                <div class="wc-desc">{w['desc']} &nbsp;·&nbsp; Feels like {w['feels']}°C</div>
                <div class="wc-detail">
                    Humidity {w['humidity']}%
                    &nbsp;&nbsp;·&nbsp;&nbsp;
                    Wind {w['wind']} km/h
                </div>
            </div>""", unsafe_allow_html=True)
            spacer(24)

            if fc:
                sec("5-Day Forecast")
                cols=st.columns(len(fc),gap="medium")
                for col,day in zip(cols,fc):
                    with col:
                        st.markdown(f"""
                        <div class="fc-card">
                            <div class="fc-date">{day['date'][5:]}</div>
                            <div class="fc-temp-hi">{day['max']}°</div>
                            <div class="fc-temp-lo">{day['min']}° low</div>
                            <div class="fc-desc">{day['desc']}</div>
                        </div>""", unsafe_allow_html=True)
        else:
            st.warning("Could not fetch weather. Check your OpenWeatherMap API key or city name.")
            st.info("Get a free API key at openweathermap.org")

# ════════════════════════════════════════════════════════════════════════════
# AI TOOLS
# ════════════════════════════════════════════════════════════════════════════
elif page == "tools":
    st.markdown("## AI Tools")
    st.markdown("Powerful extras to make your travel planning complete.")
    spacer(16)

    tool=st.selectbox("Choose a Tool",[
        "Surprise Destination Generator",
        "Local Phrases & Language Guide",
        "Packing List Generator",
        "Budget Saving Tips",
        "Side-by-Side Trip Comparison",
    ])
    spacer(14)

    if tool=="Surprise Destination Generator":
        sec("Let AI Pick Your Next Adventure")
        with st.form("sf"):
            c1,c2=st.columns(2)
            with c1: s_budget=st.number_input(f"Budget ({user_currency})",200.0,50000.0,2000.0,100.0)
            with c2: s_type=st.selectbox("Travel Style",["Budget Backpacker","Mid-Range Explorer","Luxury Traveler","Adventure Seeker","Family Trip"])
            s_act=st.text_input("Your Interests",placeholder="e.g. beaches, culture, food, adventure")
            spacer(4)
            if st.form_submit_button("Surprise Me!",use_container_width=True):
                with st.spinner("Finding your perfect destination…"):
                    st.session_state.surprise=generate_surprise(s_type,s_budget,s_act)
        if st.session_state.surprise:
            with st.container(border=True):
                st.markdown(st.session_state.surprise)

    elif tool=="Local Phrases & Language Guide":
        sec("Essential Local Phrases")
        with st.form("pf"):
            p_dest=st.text_input("Destination",placeholder="e.g. Japan, Italy, Thailand")
            spacer(4)
            pbtn=st.form_submit_button("Generate Phrases",use_container_width=True)
        if pbtn and p_dest:
            with st.spinner("Building language guide…"):
                st.session_state.phrases=generate_phrases(p_dest)
        if st.session_state.phrases:
            with st.container(border=True): st.markdown(st.session_state.phrases)

    elif tool=="Packing List Generator":
        sec("Smart Packing List")
        with st.form("plf"):
            c1,c2=st.columns(2)
            with c1:
                pk_dest=st.text_input("Destination")
                pk_days=st.number_input("Days",1,60,7)
            with c2:
                pk_type=st.selectbox("Style",["Budget Backpacker","Mid-Range Explorer","Luxury Traveler","Adventure Seeker"])
                pk_act=st.text_input("Activities")
            spacer(4)
            plbtn=st.form_submit_button("Generate Packing List",use_container_width=True)
        if plbtn and pk_dest:
            with st.spinner("Building your packing list…"):
                st.session_state.packing_list=generate_packing_list(pk_dest,pk_days,pk_type,pk_act)
        if st.session_state.packing_list:
            with st.container(border=True): st.markdown(st.session_state.packing_list)

    elif tool=="Budget Saving Tips":
        sec("Money-Saving Tips")
        with st.form("tf"):
            c1,c2=st.columns(2)
            with c1: t_dest=st.text_input("Destination")
            with c2: t_bud=st.number_input(f"Budget ({user_currency})",100.0,100000.0,1500.0,50.0)
            t_type=st.selectbox("Style",["Budget Backpacker","Mid-Range Explorer","Luxury Traveler"])
            spacer(4)
            tbtn=st.form_submit_button("Get Tips",use_container_width=True)
        if tbtn and t_dest:
            with st.spinner("Generating budget tips…"):
                st.session_state.budget_tips=generate_budget_tips(t_dest,t_bud,t_type)
        if st.session_state.budget_tips:
            with st.container(border=True): st.markdown(st.session_state.budget_tips)

    elif tool=="Side-by-Side Trip Comparison":
        sec("Compare Two Trips")
        my_trips=get_user_itineraries(st.session_state.username)
        if len(my_trips)<2:
            st.markdown("""<div class="info-box" style="max-width:500px">
                <div class="ib-title">Need 2 trips</div>
                <div class="ib-sub">You need at least 2 saved trips to compare. Go plan more adventures!</div>
            </div>""", unsafe_allow_html=True)
        else:
            labels={r["id"]:r.get("destination","?") for r in my_trips}
            c1,c2=st.columns(2)
            with c1: t1_id=st.selectbox("Trip 1",list(labels.keys()),format_func=lambda x:labels[x],key="cmp1")
            with c2: t2_id=st.selectbox("Trip 2",list(labels.keys()),format_func=lambda x:labels[x],key="cmp2",index=min(1,len(my_trips)-1))
            r1=next(r for r in my_trips if r["id"]==t1_id)
            r2=next(r for r in my_trips if r["id"]==t2_id)
            spacer(12)
            cc1,cc2=st.columns(2,gap="large")
            for col,rec in [(cc1,r1),(cc2,r2)]:
                with col:
                    exp=get_trip_expenses(rec["id"]); spent=sum(e.get("amount",0) for e in exp)
                    st.markdown(f"""
                    <div class="trip-card">
                        <h4>{rec.get('destination','?')}</h4>
                        <p><strong>Days:</strong> {rec.get('days','?')}</p>
                        <p><strong>Budget:</strong> ${rec.get('budget',0):,.0f}</p>
                        <p><strong>Style:</strong> {rec.get('travel_type','—')}</p>
                        <p><strong>Start:</strong> {rec.get('start_date','?')}</p>
                        <p><strong>Activities:</strong> {rec.get('activities','—')}</p>
                        <p><strong>Spent:</strong> ${spent:,.0f}</p>
                    </div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# PLACES  — Hotel, Restaurant & Attraction Suggestions
# ════════════════════════════════════════════════════════════════════════════
elif page == "places":
    st.markdown("## Places & Recommendations")
    st.markdown("AI-powered hotel, restaurant, and attraction suggestions for any destination worldwide.")
    spacer(16)

    p1, p2, p3 = st.columns([2,1,1], gap="medium")
    with p1: pl_dest = st.text_input("Destination", placeholder="e.g. Paris, Bali, Tokyo, Colombo")
    with p2: pl_budget = st.number_input("Budget", min_value=100.0, value=1500.0, step=50.0)
    with p3: pl_currency = st.selectbox("Currency", CURRENCY_LIST,
                 index=CURRENCY_LIST.index(user_currency) if user_currency in CURRENCY_LIST else 0)
    p4, p5, p6 = st.columns([1,1,1], gap="medium")
    with p4: pl_style = st.selectbox("Travel Style",
                   ["Budget Backpacker","Mid-Range Explorer","Luxury Traveler",
                    "Family Trip","Solo Adventure","Romantic Getaway","Business Trip"])
    with p5: pl_travelers = st.number_input("Travelers", min_value=1, max_value=20, value=1)
    with p6: pl_meal = st.selectbox("Dietary Preference",
                   ["No preference","Vegetarian","Vegan","Halal","Kosher","Gluten-free"])
    pl_accommodation = st.selectbox("Preferred Accommodation",
                   ["Any","Hotel","Hostel / Dorm","Airbnb / Apartment",
                    "Boutique Hotel","Resort","Camping / Glamping"])
    pl_acts = st.text_input("Interests", placeholder="e.g. beaches, culture, nightlife, food tours")
    pl_days = st.number_input("Trip Duration (days)", min_value=1, max_value=60, value=5)

    spacer(8)
    if not pl_dest.strip():
        st.info("Enter a destination above, then click a suggestion button below.")
    else:
        sec("Choose what to discover")
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            hotel_btn = st.button("Find Hotels & Stays", use_container_width=True)
        with c2:
            rest_btn  = st.button("Find Restaurants", use_container_width=True)
        with c3:
            attr_btn  = st.button("Top Attractions", use_container_width=True)

        if hotel_btn:
            with st.spinner(f"Finding the best hotels in {pl_dest}..."):
                result = generate_hotel_suggestions(pl_dest, pl_budget, pl_style,
                                                    pl_travelers, pl_accommodation, pl_currency)
                st.session_state["places_hotels"] = result
                st.session_state["places_dest"]   = pl_dest

        if rest_btn:
            with st.spinner(f"Finding top restaurants in {pl_dest}..."):
                result = generate_restaurant_suggestions(pl_dest, pl_meal, pl_style,
                                                         pl_travelers, pl_currency)
                st.session_state["places_restaurants"] = result
                st.session_state["places_dest"]        = pl_dest

        if attr_btn:
            with st.spinner(f"Finding top attractions in {pl_dest}..."):
                result = generate_attraction_suggestions(pl_dest, pl_style, pl_acts, pl_days)
                st.session_state["places_attractions"] = result
                st.session_state["places_dest"]        = pl_dest

        spacer(16)
        dest_label = st.session_state.get("places_dest", pl_dest)

        if st.session_state.get("places_hotels"):
            sec(f"Hotels & Stays — {dest_label}")
            with st.container(border=True):
                st.markdown(st.session_state["places_hotels"])

        if st.session_state.get("places_restaurants"):
            sec(f"Restaurants — {dest_label}")
            with st.container(border=True):
                st.markdown(st.session_state["places_restaurants"])

        if st.session_state.get("places_attractions"):
            sec(f"Top Attractions — {dest_label}")
            with st.container(border=True):
                st.markdown(st.session_state["places_attractions"])

# ════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# PROFILE PAGE
# ════════════════════════════════════════════════════════════════════════════
elif page == "settings":
    uinfo       = get_user_info(st.session_state.username)
    photo_bytes = get_profile_photo(st.session_state.username)
    joined      = str(uinfo.get("created_at",""))[:10] or "—"
    last_login  = str(uinfo.get("last_login",""))[:16] or "—"
    trip_count  = get_user_trip_count(st.session_state.username)
    all_trips   = get_user_itineraries(st.session_state.username)
    starred_cnt = sum(1 for t in all_trips if t.get("starred"))
    dests_cnt   = len(set(t.get("destination","") for t in all_trips if t.get("destination")))

    st.markdown("## Settings")
    spacer(10)

    # ── TOP: profile banner ──────────────────────────────────────────────────
    banner_left, banner_right = st.columns([1, 3], gap="large")

    with banner_left:
        if photo_bytes:
            b64 = base64.b64encode(photo_bytes).decode()
            st.markdown(f"""
            <div style="text-align:center;padding:10px 0 6px 0;">
                <img src="data:image/jpeg;base64,{b64}"
                     style="width:150px;height:150px;border-radius:50%;
                            object-fit:cover;border:4px solid #2e7d32;
                            box-shadow:0 6px 22px rgba(27,94,32,0.25);">
            </div>""", unsafe_allow_html=True)
        else:
            _ini = "".join(w[0].upper() for w in uinfo.get("full_name", st.session_state.username).split()[:2]) or "U"
            st.markdown(f"""
            <div style="text-align:center;padding:10px 0 6px 0;">
                <div style="width:150px;height:150px;border-radius:50%;
                            background:linear-gradient(135deg,#1b5e20,#388e3c);
                            display:flex;align-items:center;justify-content:center;
                            font-size:52px;font-weight:900;color:#fff;
                            border:4px solid #2e7d32;margin:0 auto;
                            box-shadow:0 6px 22px rgba(27,94,32,0.25);">{_ini}</div>
                <div style="margin-top:8px;font-size:13px;color:#64748b;">No photo uploaded</div>
            </div>""", unsafe_allow_html=True)
        spacer(8)
        up = st.file_uploader("Upload photo", type=["jpg","jpeg","png","webp"],
                              key="settings_photo_uploader")
        if up:
            raw = up.read()
            if len(raw) > 5 * 1024 * 1024:
                st.error("Image must be under 5 MB.")
            else:
                update_user_profile(st.session_state.username, profile_photo=raw)
                st.success("Photo updated!"); st.rerun()
        if photo_bytes:
            spacer(4)
            if st.button("Remove Photo", use_container_width=True, key="s_remove_photo"):
                conn = get_db(); cur = conn.cursor()
                cur.execute("UPDATE users SET profile_photo=NULL WHERE username=%s",
                            (st.session_state.username,))
                cur.close(); conn.close()
                st.success("Photo removed."); st.rerun()

    with banner_right:
        st.markdown(f"""
        <div style="background:#f0fdf4;border-radius:18px;padding:24px 28px;
                    border:1.5px solid #c8e6c9;margin-bottom:16px;">
            <div style="font-size:22px;font-weight:900;color:#1b5e20;margin-bottom:2px;">
                {uinfo.get("full_name", st.session_state.username)}</div>
            <div style="font-size:14px;color:#64748b;margin-bottom:18px;">
                @{st.session_state.username}</div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
                <div>
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                                color:#64748b;font-weight:700;">Email</div>
                    <div style="font-size:14px;color:#1e293b;font-weight:600;margin-top:2px;">
                        {uinfo.get("email","—") or "—"}</div>
                </div>
                <div>
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                                color:#64748b;font-weight:700;">Currency</div>
                    <div style="font-size:14px;color:#1e293b;font-weight:600;margin-top:2px;">
                        {uinfo.get("pref_currency","USD")}</div>
                </div>
                <div>
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                                color:#64748b;font-weight:700;">Role</div>
                    <div style="font-size:14px;color:#1e293b;font-weight:600;margin-top:2px;
                                text-transform:capitalize;">{uinfo.get("role","user")}</div>
                </div>
                <div>
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                                color:#64748b;font-weight:700;">Member Since</div>
                    <div style="font-size:14px;color:#1e293b;font-weight:600;margin-top:2px;">
                        {joined}</div>
                </div>
                <div>
                    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                                color:#64748b;font-weight:700;">Last Login</div>
                    <div style="font-size:14px;color:#1e293b;font-weight:600;margin-top:2px;">
                        {last_login}</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)
        kpi_row([
            ("✈️", trip_count,   "Total Trips"),
            ("⭐", starred_cnt,  "Starred"),
            ("🌍", dests_cnt,    "Destinations"),
        ])

    spacer(28)
    st.markdown('<hr style="border:none;border-top:1.5px solid #e8f5e9;margin:0 0 24px 0">', unsafe_allow_html=True)

    # ── BOTTOM: Edit Profile + Change Password ───────────────────────────────
    edit_col, pw_col = st.columns(2, gap="large")

    with edit_col:
        st.markdown("### Edit Profile")
        spacer(4)
        with st.form("profile_form"):
            p_name  = st.text_input("Full Name",  value=uinfo.get("full_name",""))
            p_email = st.text_input("Email",      value=uinfo.get("email",""))
            p_curr  = st.selectbox("Preferred Currency", CURRENCY_LIST,
                          index=CURRENCY_LIST.index(uinfo.get("pref_currency","USD"))
                          if uinfo.get("pref_currency","USD") in CURRENCY_LIST else 0)
            spacer(4)
            if st.form_submit_button("Save Profile", use_container_width=True):
                update_user_profile(st.session_state.username,
                                    full_name=p_name, email=p_email, pref_currency=p_curr)
                st.success("Profile updated!"); st.rerun()

    with pw_col:
        st.markdown("### Change Password")
        spacer(4)
        with st.form("pw_form"):
            old_pw  = st.text_input("Current Password", type="password")
            new_pw  = st.text_input("New Password",     type="password",
                                    placeholder="Min 6 chars + 1 number")
            new_pw2 = st.text_input("Confirm Password", type="password")
            spacer(4)
            if st.form_submit_button("Update Password", use_container_width=True):
                if not authenticate(st.session_state.username, old_pw):
                    st.error("Current password is incorrect.")
                elif new_pw != new_pw2:
                    st.error("Passwords do not match.")
                elif len(new_pw) < 6 or not re.search(r'\d', new_pw):
                    st.error("Password must be 6+ chars and contain a number.")
                else:
                    update_password(st.session_state.username, new_pw)
                    st.success("Password updated successfully!")
        if 'new_pw' in dir() and new_pw:
            strength = pw_strength(new_pw)
            clr = {"Very Weak":"#ef4444","Weak":"#f97316","Fair":"#eab308",
                   "Strong":"#22c55e","Very Strong":"#16a34a"}.get(strength,"#94a3b8")
            st.markdown(f'<p style="font-size:14px;color:{clr};font-weight:700">'
                        f'Strength: {strength}</p>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
elif page == "admin":
    if uinfo.get("role") != "admin":
        st.error("Access denied. Admin accounts only.")
        st.stop()

    st.markdown("## Admin Dashboard")
    st.markdown("System-wide management — users, admins, trips and analytics.")
    spacer(20)

    # ── KPI row ──────────────────────────────────────────────────────────────
    uc, ac, tc, tb = get_system_stats()
    kpi_row([
        ("Users",  uc,             "Registered Users"),
        ("Admins", ac,             "Admin Accounts"),
        ("Trips",  tc,             "Total Trips"),
        ("Budget", f"${tb:,.0f}", "Total Budget (All Users)"),
    ])
    spacer(28)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_users, tab_admins, tab_trips = st.tabs(["Users", "Admins", "All Trips"])

    # ── USERS TAB ─────────────────────────────────────────────────────────────
    with tab_users:
        spacer(12)
        sec("Registered Users")
        all_users = load_users()
        if not all_users:
            st.info("No regular users registered yet.")
        else:
            for uname_k, udata in all_users.items():
                trip_count = get_user_trip_count(uname_k)
                card_col, del_col = st.columns([6, 1], gap="small")
                with card_col:
                    st.markdown(f"""
                    <div style="background:#ffffff;border:1.5px solid #c8e6c9;border-radius:14px;
                         padding:16px 22px;margin-bottom:4px;box-shadow:0 2px 8px rgba(27,94,32,0.07)">
                        <div style="font-size:17px;font-weight:800;color:#1b5e20 !important;
                             margin-bottom:6px">{uname_k}</div>
                        <div style="display:flex;gap:28px;flex-wrap:wrap">
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Name:</b> {udata.get('name','—')}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Email:</b> {udata.get('email') or '—'}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Last login:</b> {udata.get('last_login','Never')}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Trips:</b> {trip_count}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Since:</b> {udata.get('created_at','—')}
                            </span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                with del_col:
                    spacer(8)
                    if st.button("Delete", key=f"adm_del_u_{uname_k}", use_container_width=True):
                        delete_user(uname_k); st.rerun()
                spacer(4)

    # ── ADMINS TAB ────────────────────────────────────────────────────────────
    with tab_admins:
        spacer(12)
        sec("Admin Accounts")
        all_admins = load_admins()
        for aname_k, adata in all_admins.items():
            protected = (aname_k == "admin")
            card_col, del_col = st.columns([6, 1], gap="small")
            with card_col:
                badge = ('<span style="background:#e8f5e9;color:#1b5e20 !important;font-size:12px;'
                         'font-weight:700;border-radius:99px;padding:2px 10px;margin-left:8px">'
                         'Protected</span>' if protected else '')
                st.markdown(f"""
                <div style="background:#ffffff;border:1.5px solid #c8e6c9;border-radius:14px;
                     padding:16px 22px;margin-bottom:4px;box-shadow:0 2px 8px rgba(27,94,32,0.07)">
                    <div style="font-size:17px;font-weight:800;color:#1b5e20 !important;
                         margin-bottom:6px">{aname_k}{badge}</div>
                    <div style="display:flex;gap:28px;flex-wrap:wrap">
                        <span style="font-size:14px;color:#334155 !important">
                            <b style="color:#1b5e20 !important">Name:</b> {adata.get('name','—')}
                        </span>
                        <span style="font-size:14px;color:#334155 !important">
                            <b style="color:#1b5e20 !important">Email:</b> {adata.get('email') or '—'}
                        </span>
                        <span style="font-size:14px;color:#334155 !important">
                            <b style="color:#1b5e20 !important">Last login:</b> {adata.get('last_login','Never')}
                        </span>
                        <span style="font-size:14px;color:#334155 !important">
                            <b style="color:#1b5e20 !important">Since:</b> {adata.get('created_at','—')}
                        </span>
                    </div>
                </div>""", unsafe_allow_html=True)
            with del_col:
                spacer(8)
                if not protected:
                    if st.button("Delete", key=f"adm_del_a_{aname_k}", use_container_width=True):
                        delete_admin(aname_k); st.rerun()
            spacer(4)

        spacer(16)
        st.markdown("### Register New Admin")
        spacer(8)
        with st.form("adm_panel_reg", clear_on_submit=True):
            pr1, pr2 = st.columns(2, gap="medium")
            with pr1:
                nrn = st.text_input("Full Name",        placeholder="Administrator name")
                nru = st.text_input("Username",         placeholder="3+ chars")
            with pr2:
                nre = st.text_input("Email (optional)", placeholder="admin@company.com")
                nrp = st.text_input("Password", type="password",
                                    placeholder="8+ chars, upper, number, symbol")
            spacer(4)
            if st.form_submit_button("Create Admin Account", use_container_width=True):
                ok, msg = register_admin(nru, nrp, nrn, nre)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()

    # ── ALL TRIPS TAB ─────────────────────────────────────────────────────────
    with tab_trips:
        spacer(12)
        sec("All Trips — System Wide")
        all_trips = load_all_itineraries()
        if not all_trips:
            st.info("No trips in the system yet.")
        else:
            # Search filter
            search_q = st.text_input("Search by destination or user", placeholder="Type to filter...",
                                     key="adm_trip_search")
            filtered = [r for r in all_trips
                        if not search_q
                        or search_q.lower() in r.get("destination","").lower()
                        or search_q.lower() in r.get("user","").lower()]

            st.markdown(f'<p style="font-size:15px;color:#475569;margin-bottom:12px">'
                        f'Showing {len(filtered)} of {len(all_trips)} trips</p>',
                        unsafe_allow_html=True)

            for rec in filtered:
                card_col, del_col = st.columns([6, 1], gap="small")
                with card_col:
                    st.markdown(f"""
                    <div style="background:#ffffff;border:1.5px solid #c8e6c9;border-radius:14px;
                         padding:16px 22px;margin-bottom:4px;box-shadow:0 2px 8px rgba(27,94,32,0.07)">
                        <div style="font-size:17px;font-weight:800;color:#1b5e20 !important;
                             margin-bottom:6px">{rec.get('destination','Unknown')}</div>
                        <div style="display:flex;gap:24px;flex-wrap:wrap">
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">User:</b> {rec.get('user','?')}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Days:</b> {rec.get('days','?')}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Budget:</b> ${rec.get('budget',0):,.0f}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Style:</b> {rec.get('travel_type','—')}
                            </span>
                            <span style="font-size:14px;color:#334155 !important">
                                <b style="color:#1b5e20 !important">Saved:</b> {rec.get('saved_on','?')}
                            </span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                with del_col:
                    spacer(8)
                    if st.button("Delete", key=f"adm_del_t_{rec['id']}", use_container_width=True):
                        admin_delete_itinerary(rec["id"]); st.rerun()
                spacer(4)
