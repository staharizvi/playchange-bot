import time
import random
import csv
import io
import os
import json
import traceback
from datetime import datetime
from pathlib import Path
import streamlit as st
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, InvalidTargetUser, UserNotFound,
    PleaseWaitFewMinutes, LoginRequired, ChallengeRequired,
    TwoFactorRequired
)

SESSION_DIR = Path(__file__).parent / "sessions"
SESSION_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Playchange DM Bot", page_icon="📩", layout="centered")

st.title("📩 Playchange Instagram DM Bot")
st.markdown("---")

# --- Log State ---
if "logs" not in st.session_state:
    st.session_state.logs = []

def add_log(level, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.logs.append({"time": timestamp, "level": level, "message": message})

# --- Sidebar: Credentials ---
with st.sidebar:
    st.header("🔐 Instagram Login")
    username = st.text_input("Username", placeholder="your_username")
    password = st.text_input("Password", type="password", placeholder="your_password")
    verification_code = st.text_input("2FA / Verification Code (if needed)", placeholder="123456")
    st.markdown("---")
    st.header("⚙️ Settings")
    delay_min = st.slider("Min delay (seconds)", 5, 30, 10)
    delay_max = st.slider("Max delay (seconds)", 10, 60, 20)

# --- Message Manager ---
st.subheader("✉️ Messages")

if "messages" not in st.session_state:
    st.session_state.messages = ["Hey! Just wanted to reach out 👋"]

# Add new message
with st.expander("➕ Add a message"):
    new_msg = st.text_area("New message", height=100, key="new_msg_input")
    if st.button("Add"):
        if new_msg.strip():
            st.session_state.messages.append(new_msg.strip())
            st.rerun()

# List & manage saved messages
if st.session_state.messages:
    for i, msg in enumerate(st.session_state.messages):
        with st.expander(f"Message {i+1}: {msg[:60]}{'...' if len(msg) > 60 else ''}"):
            edited = st.text_area("Edit", value=msg, key=f"edit_{i}", height=100)
            col_save, col_del = st.columns([1, 1])
            if col_save.button("💾 Save", key=f"save_{i}"):
                st.session_state.messages[i] = edited.strip()
                st.rerun()
            if col_del.button("🗑️ Delete", key=f"del_{i}"):
                st.session_state.messages.pop(i)
                st.rerun()

st.caption(f"{len(st.session_state.messages)} message(s) — sent in rotation, one per recipient")
# The final message list used when sending
active_messages = [m for m in st.session_state.messages if m.strip()]

st.subheader("📋 Recipients")

tab_csv, tab_manual = st.tabs(["📂 Upload CSV", "✏️ Enter Manually"])

csv_usernames = []
manual_usernames = []

with tab_csv:
    uploaded_file = st.file_uploader("Upload CSV with a 'username' column", type=["csv"])
    if uploaded_file:
        content = uploaded_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        csv_usernames = [row["username"].strip() for row in reader if row.get("username", "").strip()]
        st.success(f"Loaded **{len(csv_usernames)}** usernames from CSV")

with tab_manual:
    manual_input = st.text_area(
        "Enter usernames (one per line)",
        placeholder="johndoe\njanedoe\nexample_user",
        height=150,
    )
    if manual_input.strip():
        manual_usernames = [u.strip().lstrip("@") for u in manual_input.splitlines() if u.strip()]

# Merge both sources, deduplicate
all_usernames = list(dict.fromkeys(csv_usernames + manual_usernames))

if all_usernames:
    st.success(f"**{len(all_usernames)}** unique recipient(s) ready")
    with st.expander("Preview all usernames"):
        st.write(all_usernames)

st.markdown("---")

# --- Run Button ---
run = st.button("🚀 Start Sending", use_container_width=True, type="primary")

if run:
    st.session_state.logs = []
    errors = []
    if not username or not password:
        errors.append("Instagram credentials are required.")
    if not active_messages:
        errors.append("Add at least one message.")
    if not all_usernames:
        errors.append("Please upload a CSV or enter at least one username.")
    if delay_min >= delay_max:
        errors.append("Min delay must be less than max delay.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        # Login with session reuse
        with st.spinner("Logging in to Instagram..."):
            cl = Client()
            cl.delay_range = [1, 3]
            session_file = SESSION_DIR / f"{username}_session.json"

            logged_in = False
            # Try loading existing session first
            if session_file.exists():
                add_log("INFO", f"Found saved session for @{username}, restoring...")
                try:
                    cl.load_settings(session_file)
                    cl.login(username, password)
                    cl.get_timeline_feed()
                    logged_in = True
                    add_log("SUCCESS", f"Session restored for @{username}")
                except Exception as e:
                    add_log("WARNING", f"Saved session expired [{type(e).__name__}]: {e}")
                    print(f"SESSION RESTORE ERROR:\n{traceback.format_exc()}")
                    old_settings = cl.get_settings()
                    cl = Client()
                    cl.set_settings({})
                    cl.set_uuids(old_settings["uuids"])
                    cl.delay_range = [1, 3]

            if not logged_in:
                add_log("INFO", f"Logging in fresh as @{username}...")
                try:
                    if verification_code.strip():
                        add_log("INFO", "Using 2FA verification code...")
                        cl.login(username, password, verification_code=verification_code.strip())
                    else:
                        cl.login(username, password)
                    logged_in = True
                    cl.dump_settings(session_file)
                    add_log("SUCCESS", f"Logged in as @{username} (session saved)")
                except TwoFactorRequired:
                    print(f"LOGIN TwoFactorRequired:\n{traceback.format_exc()}")
                    add_log("ERROR", "2FA code required")
                    st.error("Login failed: This account has 2FA enabled. Enter your 2FA code in the sidebar and try again.")
                    st.stop()
                except BadPassword as e:
                    print(f"LOGIN BadPassword:\n{traceback.format_exc()}")
                    err_msg = str(e).lower()
                    if "challenge" in err_msg or "checkpoint" in err_msg:
                        add_log("ERROR", "Instagram is blocking the login (challenge/checkpoint)")
                        st.error("Login blocked by Instagram. Open Instagram app on your phone, check for 'suspicious login' notification, approve it, then try again.")
                    else:
                        add_log("ERROR", f"BadPassword error: {e}")
                        st.error("Login failed: Instagram says 'incorrect password'. This can also happen if:\n"
                                 "- **2FA is enabled** — enter your code in the sidebar\n"
                                 "- **Instagram flagged the login** — open the Instagram app, approve the login, then retry\n"
                                 "- The password is actually wrong")
                    st.code(traceback.format_exc(), language="python")
                    st.stop()
                except ChallengeRequired:
                    print(f"LOGIN ChallengeRequired:\n{traceback.format_exc()}")
                    add_log("ERROR", "Instagram challenge required")
                    st.error("Login failed: Instagram is asking for verification. Open the Instagram app, approve the login attempt, then try again here.")
                    st.stop()
                except LoginRequired:
                    print(f"LOGIN LoginRequired:\n{traceback.format_exc()}")
                    add_log("ERROR", "Instagram requires verification")
                    st.error("Login failed: Instagram requires verification. Try logging in from the app first.")
                    st.stop()
                except Exception as e:
                    tb = traceback.format_exc()
                    add_log("ERROR", f"Login failed [{type(e).__name__}]: {e}")
                    print(f"LOGIN ERROR:\n{tb}")
                    st.error(f"Login failed [{type(e).__name__}]: {e}")
                    st.code(tb, language="python")
                    st.stop()

            if logged_in:
                cl.dump_settings(session_file)
                st.success(f"Logged in as @{username}")

        # Send DMs
        st.subheader("📤 Sending Messages")
        add_log("INFO", f"Starting to send DMs to {len(all_usernames)} recipient(s)")
        progress = st.progress(0)
        status_box = st.empty()
        log_display = st.empty()

        success_list, failed_list = [], []
        total = len(all_usernames)

        def render_logs():
            lines = []
            for entry in st.session_state.logs:
                icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "🚫"}.get(entry["level"], "📝")
                lines.append(f"`{entry['time']}` {icon} {entry['message']}")
            log_display.markdown("\n\n".join(lines))

        for i, uname in enumerate(all_usernames):
            message = active_messages[i % len(active_messages)]
            status_box.info(f"Sending to @{uname}... ({i+1}/{total})")
            try:
                add_log("INFO", f"Looking up @{uname}...")
                render_logs()
                user_id = cl.user_id_from_username(uname)
                cl.direct_send(message, user_ids=[user_id])
                success_list.append(uname)
                add_log("SUCCESS", f"DM sent to @{uname}")
            except UserNotFound:
                failed_list.append((uname, "User not found"))
                add_log("WARNING", f"@{uname} — User not found")
            except InvalidTargetUser:
                failed_list.append((uname, "Invalid target"))
                add_log("WARNING", f"@{uname} — Cannot DM this user")
            except PleaseWaitFewMinutes:
                failed_list.append((uname, "Rate limited"))
                add_log("ERROR", "Rate limited by Instagram — stopping early")
                render_logs()
                break
            except Exception as e:
                failed_list.append((uname, str(e)))
                add_log("WARNING", f"@{uname} — {e}")

            progress.progress((i + 1) / total)
            render_logs()

            if i < total - 1:
                delay = random.uniform(delay_min, delay_max)
                add_log("INFO", f"Waiting {delay:.1f}s...")
                render_logs()
                status_box.info(f"Waiting {delay:.1f}s before next message...")
                time.sleep(delay)

        add_log("INFO", f"Done — {len(success_list)} sent, {len(failed_list)} failed")
        render_logs()

        status_box.empty()
        st.markdown("---")
        st.subheader("📊 Summary")
        col1, col2 = st.columns(2)
        col1.metric("✅ Sent", len(success_list))
        col2.metric("❌ Failed", len(failed_list))

        if failed_list:
            with st.expander("Failed accounts"):
                for uname, reason in failed_list:
                    st.write(f"@{uname} — {reason}")
