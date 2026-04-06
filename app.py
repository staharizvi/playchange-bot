import time
import random
import csv
import io
import streamlit as st
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, InvalidTargetUser, UserNotFound,
    PleaseWaitFewMinutes, LoginRequired
)

st.set_page_config(page_title="Playchange DM Bot", page_icon="📩", layout="centered")

st.title("📩 Playchange Instagram DM Bot")
st.markdown("---")

# --- Sidebar: Credentials ---
with st.sidebar:
    st.header("🔐 Instagram Login")
    username = st.text_input("Username", placeholder="your_username")
    password = st.text_input("Password", type="password", placeholder="your_password")
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
        # Login
        with st.spinner("Logging in to Instagram..."):
            cl = Client()
            try:
                cl.login(username, password)
                st.success(f"Logged in as @{username}")
            except BadPassword:
                st.error("Login failed: incorrect password.")
                st.stop()
            except LoginRequired:
                st.error("Login failed: Instagram requires verification. Try logging in from the app first.")
                st.stop()
            except Exception as e:
                st.error(f"Login failed: {e}")
                st.stop()

        # Send DMs
        st.subheader("📤 Sending Messages")
        progress = st.progress(0)
        status_box = st.empty()
        log = st.container()

        success_list, failed_list = [], []
        total = len(all_usernames)

        for i, uname in enumerate(all_usernames):
            message = active_messages[i % len(active_messages)]
            status_box.info(f"Sending to @{uname}... ({i+1}/{total})")
            try:
                user_id = cl.user_id_from_username(uname)
                cl.direct_send(message, user_ids=[user_id])
                success_list.append(uname)
                log.success(f"✅ @{uname}")
            except UserNotFound:
                failed_list.append((uname, "User not found"))
                log.warning(f"⚠️ @{uname} — User not found")
            except InvalidTargetUser:
                failed_list.append((uname, "Invalid target"))
                log.warning(f"⚠️ @{uname} — Cannot DM this user")
            except PleaseWaitFewMinutes:
                failed_list.append((uname, "Rate limited"))
                log.error(f"🚫 Rate limited — stopping early")
                break
            except Exception as e:
                failed_list.append((uname, str(e)))
                log.warning(f"⚠️ @{uname} — {e}")

            progress.progress((i + 1) / total)

            if i < total - 1:
                delay = random.uniform(delay_min, delay_max)
                status_box.info(f"Waiting {delay:.1f}s before next message...")
                time.sleep(delay)

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
