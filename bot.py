import csv
import time
import random
from instagrapi import Client

# --- Config ---
USERNAME = "your_instagram_username"
PASSWORD = "your_instagram_password"
CSV_FILE = "users.csv"
MESSAGE = "Hey! Just wanted to reach out 👋"
DELAY_MIN = 10  # seconds between messages (min)
DELAY_MAX = 20  # seconds between messages (max)

def load_usernames(csv_file):
    usernames = []
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            username = row.get("username", "").strip()
            if username:
                usernames.append(username)
    return usernames

def send_dms():
    cl = Client()
    cl.login(USERNAME, PASSWORD)
    print(f"Logged in as {USERNAME}")

    usernames = load_usernames(CSV_FILE)
    print(f"Loaded {len(usernames)} usernames from {CSV_FILE}")

    success, failed = [], []

    for username in usernames:
        try:
            user_id = cl.user_id_from_username(username)
            cl.direct_send(MESSAGE, user_ids=[user_id])
            print(f"[OK] Sent to @{username}")
            success.append(username)
        except Exception as e:
            print(f"[FAIL] @{username}: {e}")
            failed.append(username)

        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        print(f"Waiting {delay:.1f}s...")
        time.sleep(delay)

    print(f"\nDone. Success: {len(success)}, Failed: {len(failed)}")
    if failed:
        print("Failed:", failed)

if __name__ == "__main__":
    send_dms()
