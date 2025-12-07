import streamlit as st
from audio_recorder_streamlit import audio_recorder
import os
import time
import json
from pathlib import Path
import io
import zipfile

# ---------- Configuration ----------
st.set_page_config(page_title="Speech Data Curation (Multi-user)", layout="wide")

DEFAULT_ADMIN_PASSWORD = "adminpass"
BASE_DIR = Path("recordings")
BASE_DIR.mkdir(exist_ok=True)

# ---------- Utility functions ----------
def _load_metadata(user_dir: Path):
    meta_file = user_dir / "metadata.json"
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return []
    return []

def _save_metadata(user_dir: Path, metadata):
    meta_file = user_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)

def _list_users():
    return sorted([p.name for p in BASE_DIR.iterdir() if p.is_dir()])

def _user_recordings(user_dir: Path):
    return sorted([p for p in user_dir.iterdir() if p.is_file() and p.suffix.lower() in (".wav", ".webm", ".ogg", ".mp3")])

def _make_zip_bytes(path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in path.rglob("*"):
            if f.is_file():
                z.write(f, arcname=f.relative_to(path))
    buf.seek(0)
    return buf.getvalue()

# ---------- UI ----------
st.title("🎤 Speech Data Curation — Multi-user")
st.markdown(
    "Users record from their browser. Admin can view and download every user's recordings. "
    "This is a **username-only** flow (no passwords for users)."
)

st.sidebar.header("Quick actions")
mode = st.sidebar.radio("Choose view", ["Record (User)", "Admin Dashboard"])

# ---------- USER RECORDING FLOW ----------
if mode == "Record (User)":
    st.header("User recording")
    st.info("Enter a username (no password). The app will store recordings under `recordings/{username}/`")

    username = st.text_input("Enter your username (e.g., joy, tobi, user34)", value="", max_chars=50)

    if username:
        safe_username = "".join(ch for ch in username if ch.isalnum() or ch in ("_", "-")).lower()
        if not safe_username:
            st.error("Please enter a username containing letters or numbers.")
        else:
            user_dir = BASE_DIR / safe_username
            user_dir.mkdir(parents=True, exist_ok=True)

            st.write(f"Recording as **{safe_username}**. Your recordings will be saved in `{user_dir}/`")

            with st.expander("Optional: text prompt for the speaker"):
                prompt_text = st.text_area("Prompt (e.g., sentence to read)", value="Please read this sentence aloud.", height=80)

            st.markdown("**Press the mic to start/stop recording**")
            audio_bytes = audio_recorder(
                text="Click to record",
                recording_color="#FF3333",
                neutral_color="#6aa36f"
            )

            if audio_bytes:
                ts = int(time.time())
                filename = f"{safe_username}_{ts}.wav"
                filepath = user_dir / filename
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)

                metadata = _load_metadata(user_dir)
                entry = {
                    "filename": filename,
                    "timestamp": ts,
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                    "prompt": prompt_text.strip() if prompt_text else None,
                }
                metadata.append(entry)
                _save_metadata(user_dir, metadata)

                st.success(f"Saved recording as **{filename}**")
                st.audio(audio_bytes, format="audio/wav")
                st.download_button("⬇ Download this recording", audio_bytes, file_name=filename, mime="audio/wav")

    else:
        st.warning("Enter a username to enable the recorder.")

# ---------- ADMIN DASHBOARD ----------
else:
    st.header("Admin dashboard")
    st.info("This area is protected by admin password. Set `admin_password` in Streamlit Secrets or use the default (not secure) password.")

    admin_password = st.secrets.get("admin_password", DEFAULT_ADMIN_PASSWORD) if hasattr(st, "secrets") else DEFAULT_ADMIN_PASSWORD
    entered = st.text_input("Admin password", type="password")
    if entered != admin_password:
        st.warning("Enter the admin password to continue.")
        st.stop()

    st.success("Admin authenticated")

    users = _list_users()
    st.subheader(f"Users ({len(users)})")
    if not users:
        st.info("No users yet. Users' folders will be created once they record.")
    else:
        for u in users:
            user_dir = BASE_DIR / u
            recs = _user_recordings(user_dir)
            meta = _load_metadata(user_dir)

            st.markdown(f"### 👤 {u} — {len(recs)} recordings")
            c1, c2, c3 = st.columns([2, 1, 1])

            with c1:
                if st.button(f"View recordings — {u}", key=f"view_{u}"):
                    st.markdown("---")
                    st.write(f"**Recordings for {u}**")
                    if meta:
                        for entry in reversed(meta):
                            fname = entry.get("filename")
                            ts_iso = entry.get("iso", "")
                            prompt = entry.get("prompt") or ""
                            file_path = user_dir / fname
                            if file_path.exists():
                                try:
                                    with open(file_path, "rb") as fh:
                                        audio_b = fh.read()
                                except Exception:
                                    audio_b = None

                                try:
                                    st.chat_message("user").write(f"**{u}** • {ts_iso}")
                                    if prompt:
                                        st.chat_message("assistant").write(f"_Prompt:_ {prompt}")
                                    if audio_b:
                                        st.audio(audio_b, format="audio/wav")
                                        st.download_button(
                                            "Download file", audio_b, file_name=fname, mime="audio/wav", key=f"dl_{u}_{fname}"
                                        )
                                    else:
                                        st.warning("Audio missing for this entry.")
                                except Exception:
                                    st.markdown(f"**{fname}** — {ts_iso}")
                                    if prompt:
                                        st.markdown(f"*Prompt:* {prompt}")
                                    if audio_b:
                                        st.audio(audio_b, format="audio/wav")
                                        st.download_button(
                                            "Download file", audio_b, file_name=fname, mime="audio/wav", key=f"dl2_{u}_{fname}"
                                        )
                                    else:
                                        st.warning("Audio missing for this entry.")
                    else:
                        st.info("No metadata for this user yet.")
                    st.markdown("---")

            with c2:
                if st.button(f"Download ZIP — {u}", key=f"zip_{u}"):
                    zip_bytes = _make_zip_bytes(user_dir)
                    st.download_button(label=f"⬇ Download {u}.zip", data=zip_bytes, file_name=f"{u}_recordings.zip", mime="application/zip", key=f"zipdl_{u}")

            with c3:
                if st.button(f"Delete user {u}", key=f"del_{u}"):
                    confirm = st.checkbox(f"Confirm deletion of {u}", key=f"confirm_{u}")
                    if confirm:
                        for f in user_dir.rglob("*"):
                            if f.is_file():
                                try:
                                    f.unlink()
                                except Exception:
                                    pass
                        try:
                            user_dir.rmdir()
                        except Exception:
                            pass
                        st.experimental_rerun()

    st.markdown("---")
    st.write("Admin tips:")
    st.write("- Set a strong admin password in Streamlit Secrets (key: `admin_password`).")
    st.write("- To export all users at once, download each user's ZIP from their section.")
    st.write("- Optional upgrades: global ZIP export, speaker metadata fields, Whisper transcription.")
