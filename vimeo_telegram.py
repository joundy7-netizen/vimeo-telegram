import os
import json
import time
import requests
import feedparser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ============================================================
# TELEGRAM SETTINGS
# ============================================================

TELEGRAM_BOT_TOKEN = "8763731429:AAHWisi852DKyQmLn6S_w7P-OqvzEcA_amY"
TELEGRAM_CHAT_ID = "1314820822"

# ============================================================
# CHECKING SETTINGS
# ============================================================

CHECK_EVERY = 30          # seconds between full checking rounds
MAX_WORKERS = 10          # Vimeo accounts checked at the same time
REQUEST_TIMEOUT = 15      # seconds before a Vimeo request times out
ERROR_WAIT = 5             # wait after an error before retrying

# File used to remember videos already sent
SEEN_FILE = "seen_videos.json"

# ============================================================
# VIMEO ACCOUNTS
# ============================================================

VIMEO_ACCOUNTS = [
    "https://vimeo.com/caestusfilms",
    "https://vimeo.com/user61397360",
    "https://vimeo.com/user31553251",
    "https://vimeo.com/user70803257",
    "https://vimeo.com/user47041178",
    "https://vimeo.com/swelandimad",
    "https://vimeo.com/user98079776",
    "https://vimeo.com/dkbproductions",
    "https://vimeo.com/user54343598",
    "https://vimeo.com/user52851353",
    "https://vimeo.com/user1651482",
    "https://vimeo.com/user65713847",
    "https://vimeo.com/user11052886",
    "https://vimeo.com/user79538514",
    "https://vimeo.com/user82982577",
    "https://vimeo.com/user7268771",
    "https://vimeo.com/user63102526",
    "https://vimeo.com/asmaeelmoudir",
    "https://vimeo.com/user230109589",
    "https://vimeo.com/user227853247",
    "https://vimeo.com/user189380815",
    "https://vimeo.com/user83004370",
    "https://vimeo.com/user49287087",
    "https://vimeo.com/janaprod",
    "https://vimeo.com/user215577477",
    "https://vimeo.com/user32986065",
    "https://vimeo.com/user8072778",
    "https://vimeo.com/user208405174",
    "https://vimeo.com/user52393274",
    "https://vimeo.com/laprodmaroc",
    "https://vimeo.com/user86491705",
    "https://vimeo.com/user49137742",
    "https://vimeo.com/user1143162",
    "https://vimeo.com/user44050636",
    "https://vimeo.com/dohamous",
    "https://vimeo.com/hamzaatifi",
    "https://vimeo.com/kenzatazi",
    "https://vimeo.com/user219055442",
    "https://vimeo.com/aztaleb",
    "https://vimeo.com/rachidelouali",
    "https://vimeo.com/user79215976",
    "https://vimeo.com/user41495630",
    "https://vimeo.com/user54378850",
    "https://vimeo.com/user125261456",
    "https://vimeo.com/user49481921",
    "https://vimeo.com/user45251394",
    "https://vimeo.com/user131586046",
    "https://vimeo.com/user13934302",
    "https://vimeo.com/user58235378",
    "https://vimeo.com/user56421699",
    "https://vimeo.com/user32085186",
    "https://vimeo.com/user57542025",
    "https://vimeo.com/a2lprod",
    "https://vimeo.com/user32087148",
]

# Remove accidental duplicates automatically
VIMEO_ACCOUNTS = list(dict.fromkeys(VIMEO_ACCOUNTS))


# ============================================================
# LOAD / SAVE SEEN VIDEOS
# ============================================================

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return set(data)

    except Exception as e:
        print(f"[WARNING] Could not read {SEEN_FILE}: {e}")
        return set()


def save_seen(seen):
    try:
        # Keep the file from becoming unnecessarily huge
        data = list(seen)[-5000:]

        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[WARNING] Could not save seen videos: {e}")


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if response.ok:
            return True

        print(
            f"[TELEGRAM ERROR] "
            f"{response.status_code}: {response.text[:300]}"
        )

    except requests.RequestException as e:
        print(f"[TELEGRAM ERROR] {e}")

    return False


# ============================================================
# VIMEO RSS
# ============================================================

def get_rss_url(profile_url):
    profile_url = profile_url.rstrip("/")

    return profile_url + "/videos/rss"


def check_account(profile_url):
    """
    Check one Vimeo profile.

    Returns:
        (profile_url, videos, error)
    """

    rss_url = get_rss_url(profile_url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/153 Safari/537.36"
        )
    }

    try:
        response = requests.get(
            rss_url,
            headers=headers,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return (
                profile_url,
                [],
                f"HTTP {response.status_code}"
            )

        feed = feedparser.parse(response.content)

        videos = []

        for entry in feed.entries[:10]:

            video_url = (
                entry.get("link")
                or entry.get("id")
            )

            if not video_url:
                continue

            title = (
                entry.get("title")
                or "New Vimeo video"
            )

            published = (
                entry.get("published")
                or entry.get("updated")
                or ""
            )

            videos.append({
                "id": entry.get("id") or video_url,
                "title": title,
                "url": video_url,
                "published": published,
            })

        return profile_url, videos, None

    except requests.RequestException as e:
        return profile_url, [], str(e)

    except Exception as e:
        return profile_url, [], str(e)


# ============================================================
# NOTIFICATION
# ============================================================

def make_message(profile, video):
    title = video["title"]
    url = video["url"]

    return (
        "🎬 NEW VIMEO VIDEO\n\n"
        f"🎞 {title}\n"
        f"👤 {profile}\n\n"
        f"🔗 {url}"
    )


# ============================================================
# MAIN CHECK
# ============================================================

def check_all_accounts(seen):
    print()
    print("=" * 70)
    print(
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"Checking {len(VIMEO_ACCOUNTS)} Vimeo accounts..."
    )
    print("=" * 70)

    new_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

        futures = [
            executor.submit(check_account, account)
            for account in VIMEO_ACCOUNTS
        ]

        for future in as_completed(futures):

            try:
                profile, videos, error = future.result()

            except Exception as e:
                print(f"[WORKER ERROR] {e}")
                error_count += 1
                continue

            if error:
                print(f"[ERROR] {profile} -> {error}")
                error_count += 1
                continue

            print(
                f"[OK] {profile} "
                f"({len(videos)} videos found)"
            )

            # Oldest first so notifications appear in order
            videos.reverse()

            for video in videos:

                video_id = str(video["id"])

                if video_id in seen:
                    continue

                # Mark as seen BEFORE sending.
                # This prevents duplicate messages if Telegram
                # or the next checking cycle behaves unexpectedly.
                seen.add(video_id)

                message = make_message(profile, video)

                if send_telegram(message):
                    print(
                        f"[NEW] {profile} -> "
                        f"{video['title']}"
                    )

                    new_count += 1

                else:
                    print(
                        f"[WARNING] Telegram failed for: "
                        f"{video['title']}"
                    )

    save_seen(seen)

    print()
    print(
        f"Round finished | "
        f"New: {new_count} | "
        f"Errors: {error_count}"
    )


# ============================================================
# STARTUP
# ============================================================

def main():

    print("=" * 70)
    print("VIMEO → TELEGRAM NOTIFICATION BOT")
    print("=" * 70)

    print(f"Vimeo accounts : {len(VIMEO_ACCOUNTS)}")
    print(f"Check interval : {CHECK_EVERY} seconds")
    print(f"Workers        : {MAX_WORKERS}")
    print()

    if TELEGRAM_BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        print("ERROR: Put your Telegram bot token in the script.")
        return

    if TELEGRAM_CHAT_ID == "PUT_YOUR_CHAT_ID_HERE":
        print("ERROR: Put your Telegram chat ID in the script.")
        return

    seen = load_seen()

    print(f"Previously seen videos: {len(seen)}")
    print()
    print("Bot started. Press CTRL+C to stop.")
    print()

    # --------------------------------------------------------
    # FIRST RUN
    # --------------------------------------------------------
    #
    # The first run records the existing videos without
    # sending notifications for all old uploads.
    #
    first_run = len(seen) == 0

    if first_run:
        print("[FIRST RUN] Learning existing videos...")
        print("[FIRST RUN] Old videos will NOT trigger notifications.")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            futures = [
                executor.submit(check_account, account)
                for account in VIMEO_ACCOUNTS
            ]

            for future in as_completed(futures):

                try:
                    profile, videos, error = future.result()

                    if error:
                        print(f"[FIRST RUN ERROR] {profile}: {error}")
                        continue

                    for video in videos:
                        seen.add(str(video["id"]))

                except Exception as e:
                    print(f"[FIRST RUN ERROR] {e}")

        save_seen(seen)

        print(
            f"[FIRST RUN] Saved {len(seen)} existing videos."
        )
        print("[FIRST RUN] Now monitoring for NEW uploads.")
        print()

    # --------------------------------------------------------
    # CONTINUOUS MONITORING
    # --------------------------------------------------------

    while True:

        try:
            start_time = time.time()

            check_all_accounts(seen)

            elapsed = time.time() - start_time

            # Don't start another round immediately.
            wait_time = max(
                1,
                CHECK_EVERY - elapsed
            )

            print(
                f"Next check in "
                f"{wait_time:.1f} seconds..."
            )

            time.sleep(wait_time)

        except KeyboardInterrupt:
            print()
            print("Bot stopped by user.")
            save_seen(seen)
            break

        except Exception as e:
            # Critical protection: even if something unexpected
            # happens, the entire bot doesn't die.
            print()
            print(f"[CRITICAL ERROR] {e}")
            print(
                f"Restarting checking in "
                f"{ERROR_WAIT} seconds..."
            )

            save_seen(seen)

            time.sleep(ERROR_WAIT)


if __name__ == "__main__":
    main()