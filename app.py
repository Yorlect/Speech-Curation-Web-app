"""
Yorlect - mini speech curation web app (Streamlit)

Features:
- User sign-up/login
- Admin (password via env var YORLECT_ADMIN_PASS) with exclusive dataset access
- Metadata input form (name, age, gender, locale, notes)
- Record audio via browser (streamlit-audio-recorder) or upload WAV/MP3 fallback
- Store audio files under data/{username}/ and metadata in SQLite (yorlect.db)
- Per-user progress tracking with a configurable target
- Admin can view all recordings, export CSV, download ZIP of dataset
"""

import os
import sqlite3
import uuid
import io
import zipfile
from datetime import datetime
from pathlib import Path
import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash

# Try import of recorder component (optional)
try:
    from streamlit_audio_recorder import audio_recorder
    RECORDER_AVAILABLE = True
except Exception:
    RECORDER_AVAILABLE = False

# --- Constants / settings ---
DATA_DIR = Path("data")
DB_PATH = Path("yorlect.db")
ADMIN_PASS = os.environ.get("YORLECT_ADMIN_PASS", "yorlect_admin")  
RECORDINGS_TARGET_PER_USER = 30  

DATA_DIR.mkdir(exist_ok=True)

# --- Database helpers ---
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS recordings (
        id TEXT PRIMARY KEY,
        username TEXT,
        filename TEXT,
        filepath TEXT,
        name TEXT,
        age INTEGER,
        gender TEXT,
        locale TEXT,
        notes TEXT,
        duration_seconds REAL,
        timestamp TEXT
    )""")
    conn.commit()
    return conn

conn = init_db()

def ensure_admin_user():
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE is_admin=1 LIMIT 1")
    row = cur.fetchone()
    if row is None:
        # create default admin user 'admin' with password ADMIN_PASS
        pw_hash = generate_password_hash(ADMIN_PASS)
        cur.execute(
            "INSERT OR REPLACE INTO users (username,password_hash,is_admin,created_at) VALUES (?,?,1,?)",
            ("admin", pw_hash, datetime.utcnow().isoformat()),
        )
        conn.commit()

ensure_admin_user()

# --- Auth helpers ---
def sign_up(username, password):
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE username=?", (username,))
    if cur.fetchone():
        return False, "Username already exists"
    pw_hash = generate_password_hash(password)
    cur.execute("INSERT INTO users (username,password_hash,is_admin,created_at) VALUES (?,?,0,?)",
                (username, pw_hash, datetime.utcnow().isoformat()))
    conn.commit()
    # create user data folder
    (DATA_DIR / username).mkdir(parents=True, exist_ok=True)
    return True, "User created"

def login_user(username, password):
    cur = conn.cursor()
    cur.execute("SELECT password_hash, is_admin FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row:
        return False, "No such user"
    pw_hash, is_admin = row
    if check_password_hash(pw_hash, password):
        return True, bool(is_admin)
    else:
        return False, "Incorrect password"

# --- Recording save helpers ---
def save_recording(username, file_bytes: bytes, original_filename: str, metadata: dict):
    uid = str(uuid.uuid4())
    user_dir = DATA_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix or ".wav"
    filename = f"{uid}{ext}"
    filepath = user_dir / filename
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    # try to estimate duration for WAV (simple)
    duration_seconds = None
    try:
        import wave, contextlib
        if filepath.suffix.lower() == ".wav":
            with contextlib.closing(wave.open(str(filepath),'r')) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration_seconds = frames / float(rate)
    except Exception:
        duration_seconds = None

    cur = conn.cursor()
    cur.execute("""INSERT INTO recordings 
        (id, username, filename, filepath, name, age, gender, locale, notes, duration_seconds, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, username, filename, str(filepath), metadata.get("name"), metadata.get("age"),
         metadata.get("gender"), metadata.get("locale"), metadata.get("notes"),
         duration_seconds, datetime.utcnow().isoformat()))
    conn.commit()
    return uid

def get_user_recordings(username):
    cur = conn.cursor()
    cur.execute("SELECT id, filename, filepath, name, age, gender, locale, notes, duration_seconds, timestamp FROM recordings WHERE username=? ORDER BY timestamp DESC", (username,))
    rows = cur.fetchall()
    return rows

def get_all_recordings():
    cur = conn.cursor()
    cur.execute("SELECT id, username, filename, filepath, name, age, gender, locale, notes, duration_seconds, timestamp FROM recordings ORDER BY timestamp DESC")
    return cur.fetchall()

# --- Streamlit UI ---
st.set_page_config(page_title="Yorlect", layout="wide")

if 'auth' not in st.session_state:
    st.session_state.auth = {"logged_in": False, "username": None, "is_admin": False}

def show_login():
    st.sidebar.header("Account")
    tab = st.sidebar.radio("Auth action:", ["Login", "Sign up", "Logout"])
    if tab == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            ok = login_user(username, password)
            if isinstance(ok, tuple):
                success, admin_or_msg = ok
                if success:
                    st.session_state.auth = {"logged_in": True, "username": username, "is_admin": admin_or_msg}
                    st.sidebar.success(f"Logged in as {username}")
                else:
                    st.sidebar.error(admin_or_msg)
            else:
                st.sidebar.error("Login failed")
    elif tab == "Sign up":
        username = st.sidebar.text_input("Choose username")
        password = st.sidebar.text_input("Choose password", type="password")
        confirm = st.sidebar.text_input("Confirm password", type="password")
        if st.sidebar.button("Create account"):
            if not username or not password:
                st.sidebar.error("Provide username and password")
            elif password != confirm:
                st.sidebar.error("Passwords don't match")
            else:
                ok, msg = sign_up(username, password)
                if ok:
                    st.sidebar.success("Account created — please log in")
                else:
                    st.sidebar.error(msg)
    else:  # Logout
        if st.sidebar.button("Logout"):
            st.session_state.auth = {"logged_in": False, "username": None, "is_admin": False}
            st.sidebar.success("Logged out")

show_login()

# Top nav
st.title("Yorlect — Yoruba speech curation")
st.write("Curate Yoruba speech audio and metadata. Your recordings are private to your account; admins can export datasets.")

nav = st.sidebar.selectbox("Go to", ["Home", "Record", "Metadata", "Progress", "Admin"])

username = st.session_state.auth["username"]
logged_in = st.session_state.auth["logged_in"]
is_admin = st.session_state.auth["is_admin"]

if nav == "Home":
    st.header("Home")
    st.write("""
    **Yorlect** helps you collect curated Yoruba speech recordings.
    
    Features:
    - Sign up / login and record audio (or upload)
    - Add metadata (name, age, gender, locale, notes)
    - Track your recording progress
    - Admins can export the dataset (audio + metadata)
    
    **How to use**
    1. Create an account (sidebar) or login.
    2. Fill the metadata in *Metadata* page.
    3. Record audio in *Record* page (or upload).
    4. Check progress in *Progress*.
    """)

    if not logged_in:
        st.info("Please sign up or login from the sidebar to start recording.")
    else:
        st.success(f"Logged in as **{username}**")

elif nav == "Metadata":
    st.header("Metadata for next recording")
    if not logged_in:
        st.warning("Please log in to enter metadata.")
    else:
        with st.form("metadata_form"):
            name = st.text_input("Full name (or speaker ID)", value="")
            age = st.number_input("Age", min_value=0, max_value=120, value=18)
            gender = st.selectbox("Gender", ["Prefer not to say", "Female", "Male", "Other"])
            locale = st.text_input("Locale / dialect (e.g., Oyo, Lagos)", value="")
            notes = st.text_area("Notes (context, recording conditions, mic used, etc.)")
            submitted = st.form_submit_button("Save metadata for next recording")
        if submitted:
            # store temp metadata in session so record page can use
            st.session_state['pending_metadata'] = {"name": name, "age": age, "gender": gender, "locale": locale, "notes": notes}
            st.success("Metadata saved — go to the Record page to make your recording.")

elif nav == "Record":
    st.header("Record or upload audio")
    if not logged_in:
        st.warning("Please log in to record audio.")
    else:
        pending_meta = st.session_state.get('pending_metadata', {})
        st.subheader("Metadata to attach")
        st.write("You can edit metadata here (or set it in Metadata page).")
        with st.form("meta_attach"):
            name = st.text_input("Full name / speaker ID", value=pending_meta.get("name",""))
            age = st.number_input("Age", min_value=0, max_value=120, value=pending_meta.get("age",18))
            gender = st.selectbox("Gender", ["Prefer not to say", "Female", "Male", "Other"], index=0)
            locale = st.text_input("Locale / dialect", value=pending_meta.get("locale",""))
            notes = st.text_area("Notes", value=pending_meta.get("notes",""))
            save_meta = st.form_submit_button("Use this metadata for recording")
        if save_meta:
            metadata = {"name": name, "age": age, "gender": gender, "locale": locale, "notes": notes}
            st.session_state['pending_metadata'] = metadata
            st.success("Metadata attached for next recording.")

        st.markdown("---")
        st.subheader("Record in browser (recommended)")
        recorded_bytes = None
        if RECORDER_AVAILABLE:
            # audio_recorder returns bytes if recording completed
            st.write("Click the record button below, then stop when done.")
            rec = audio_recorder()
            if rec is not None:
                recorded_bytes = rec
        else:
            st.info("Browser recorder component not installed. Use file uploader below (WAV/MP3).")
        st.markdown("---")
        st.subheader("Or upload a file (WAV/MP3)")
        uploaded = st.file_uploader("Upload audio file", type=["wav","mp3","m4a","ogg"])
        if uploaded is not None:
            uploaded_bytes = uploaded.read()
            recorded_bytes = uploaded_bytes
            original_filename = uploaded.name
        else:
            original_filename = f"recording.wav"

        if recorded_bytes:
            st.audio(recorded_bytes)
            if st.button("Save recording to dataset"):
                metadata = st.session_state.get('pending_metadata', {"name": None, "age": None, "gender": None, "locale": None, "notes": None})
                uid = save_recording(username, recorded_bytes, original_filename, metadata)
                st.success(f"Saved recording (id={uid})")
                # clear pending metadata after save
                st.session_state['pending_metadata'] = {}
        st.markdown("---")
        st.subheader("Your recent recordings")
        rows = get_user_recordings(username)
        if not rows:
            st.info("No recordings yet.")
        else:
            for r in rows[:10]:
                rid, fname, fp, name_, age_, gender_, locale_, notes_, dur, ts = r
                st.write(f"**{fname}** — {ts} — name:{name_} age:{age_} locale:{locale_} dur:{dur}")
                try:
                    with open(fp, "rb") as f:
                        st.audio(f.read())
                except Exception:
                    st.write("Could not load file preview.")

elif nav == "Progress":
    st.header("Your progress")
    if not logged_in:
        st.warning("Please log in to see your progress.")
    else:
        rows = get_user_recordings(username)
        n = len(rows)
        st.metric("Recordings completed", n)
        progress = min(n / RECORDINGS_TARGET_PER_USER, 1.0)
        st.progress(progress)
        st.write(f"{n} / {RECORDINGS_TARGET_PER_USER} recordings")
        # breakdown: total duration if available
        total_seconds = sum([r[8] or 0 for r in rows])
        if total_seconds:
            minutes = total_seconds / 60
            st.write(f"Total recorded time: {minutes:.1f} minutes")
        st.markdown("### Recent recordings")
        for r in rows[:20]:
            rid, fname, fp, name_, age_, gender_, locale_, notes_, dur, ts = r
            st.write(f"- {fname} — {ts} — {name_} — {locale_}")

elif nav == "Admin":
    st.header("Admin panel")
    # check admin status
    if not logged_in or not is_admin:
        st.warning("Admin access only. Log in as admin.")
        st.info("Admin account was created automatically. Default username: `admin`. Set env var YORLECT_ADMIN_PASS before first run to change the default password.")
    else:
        st.subheader("All recordings (admin view)")
        all_rows = get_all_recordings()
        st.write(f"Total recordings: {len(all_rows)}")
        # show simple table
        import pandas as pd
        df = pd.DataFrame(all_rows, columns=["id","username","filename","filepath","name","age","gender","locale","notes","duration_seconds","timestamp"])
        st.dataframe(df)

        if st.button("Export metadata CSV"):
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download metadata CSV", data=csv_bytes, file_name="yorlect_metadata.csv", mime="text/csv")

        # create zip of all audio files
        if st.button("Create ZIP of all audio files"):
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in all_rows:
                    _, username_r, filename_r, filepath_r, *_ = r
                    try:
                        zf.write(filepath_r, arcname=f"{username_r}/{filename_r}")
                    except Exception as e:
                        st.write(f"Skipping {filepath_r}: {e}")
            zip_buf.seek(0)
            st.download_button("Download dataset ZIP", data=zip_buf, file_name="yorlect_dataset.zip", mime="application/zip")

        st.markdown("---")
        st.subheader("Manage users")
        cur = conn.cursor()
        cur.execute("SELECT username, is_admin, created_at FROM users")
        users = cur.fetchall()
        st.write("Registered users:")
        for u in users:
            st.write(f"- {u[0]} (admin: {bool(u[1])}) created: {u[2]}")

        st.markdown("**Danger zone**")
        if st.button("Delete all recordings (IRREVERSIBLE)"):
            if st.checkbox("I understand this will delete all audio and metadata"):
                # delete files
                for p in DATA_DIR.glob("*"):
                    if p.is_dir():
                        for f in p.glob("*"):
                            try:
                                f.unlink()
                            except:
                                pass
                        try:
                            p.rmdir()
                        except:
                            pass
                # drop recordings
                cur.execute("DELETE FROM recordings")
                conn.commit()
                st.success("All recordings deleted.")
