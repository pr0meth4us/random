#!/usr/bin/env python3
"""
tiktok_streak_keeper.py
-----------------------
Browser automation script using Playwright to maintain TikTok streaks
by sending daily direct messages to friends.
"""

import argparse
import os
import random
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Stealth plugin to patch browser fingerprint leaks
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None

# Load environment variables if running directly
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_DIR = SCRIPT_DIR / "tiktok_session"
STATE_FILE = SCRIPT_DIR / "state.json"

# Realistic desktop user agents to rotate through
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Realistic viewport sizes to randomize
_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]


def _human_delay(page, min_ms: int = 800, max_ms: int = 2500):
    """Wait a randomized human-like duration."""
    page.wait_for_timeout(random.randint(min_ms, max_ms))


def _human_pause_between_friends():
    """Return a gaussian-distributed delay in seconds for pausing between friends."""
    delay = int(random.gauss(45, 20))
    return max(15, min(delay, 120))


def load_state_from_db() -> str | None:
    """
    Attempts to connect to MongoDB and retrieve the stored TikTok state JSON.
    """
    import os
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME", "expTracker")
    if not mongo_uri:
        return None
        
    try:
        from pymongo import MongoClient
        print("Connecting to MongoDB to fetch TikTok state...")
        client = MongoClient(mongo_uri)
        db = client[db_name]
        doc = db["tiktok_settings"].find_one({"key": "state_json"})
        if doc and "value" in doc:
            print("Successfully retrieved TikTok state from MongoDB.")
            return doc["value"]
    except Exception as e:
        print(f"Warning: Failed to fetch TikTok state from MongoDB: {e}")
    return None


def save_state_to_db(state_json: str) -> None:
    """
    Attempts to connect to MongoDB and save the updated TikTok state JSON.
    """
    import os
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME", "expTracker")
    if not mongo_uri:
        return
        
    try:
        from pymongo import MongoClient
        print("Connecting to MongoDB to save TikTok state...")
        client = MongoClient(mongo_uri)
        db = client[db_name]
        db["tiktok_settings"].update_one(
            {"key": "state_json"},
            {"$set": {"value": state_json, "updated_at": time.time()}},
            upsert=True
        )
        print("Successfully saved TikTok state to MongoDB.")
    except Exception as e:
        print(f"Warning: Failed to save TikTok state to MongoDB: {e}")


def login_mode() -> None:
    """
    Launches Chrome in headed mode so the user can log in manually
    and saves the session context.
    """
    print("\n=== TikTok Streak Keeper: Login Mode ===")
    print("Launching headed browser. Please log into your TikTok account.")
    print("Once logged in, close the browser window or wait 60 seconds to save session.")
    print(f"Persistent session will be stored in: {SESSION_DIR}")
    print(f"State JSON will be exported to: {STATE_FILE}\n")

    SESSION_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = browser.pages[0]
        page.goto("https://www.tiktok.com/")

        # Keep browser open until either 60 seconds pass or the user closes it manually
        start_time = time.time()
        try:
            while time.time() - start_time < 60:
                if len(browser.pages) > 0 and not page.is_closed():
                    page.wait_for_timeout(1000)
                else:
                    break
        except Exception:
            pass

        # Save cookies/localStorage state to state.json
        browser.storage_state(path=STATE_FILE)
        print(f"\nStorage state exported successfully to: {STATE_FILE}")
        print("Session saved successfully. You can now run the script in automation mode.")
        browser.close()


def generate_streak_message_pool() -> list[str]:
    import random
    greetings = [
        "Hey", "Hello", "Hi", "Yo", "Hey there", "Hey friend", "Hi there", "What's up",
        "How's it going", "Morning", "Evening", "Hello hello", "Heyyo", "Hey hey", "Quick hi"
    ]
    phrases = [
        "just keeping our streak alive", "hope you're having a great day", "hope all is well",
        "sending you some good vibes", "hope your week is going great", "have a fantastic day ahead",
        "wishing you an awesome day", "hope you're doing well", "just staying connected",
        "hope you have a wonderful day", "streak keeper time", "hope your day is going well"
    ]
    emojis = ["🔥", "✨", "😊", "👋", "🙌", "⚡", "🌟", "😎", "✌️", "💯", "🎉", "🍀", "☀️", "🌈", "🎈"]
    follow_ups = [
        "how are things?", "any plans for today?", "what are you up to?", "have a good one!",
        "catch up soon!", "talk to you later!", "hope you have fun today!", "doing anything exciting?",
        "let me know how it goes!", "have an awesome day!"
    ]
    
    pool = set()
    random_gen = random.Random()
    while len(pool) < 500:
        g = random_gen.choice(greetings)
        p = random_gen.choice(phrases)
        e = random_gen.choice(emojis)
        f = random_gen.choice(follow_ups)
        structure = random_gen.choice([1, 2, 3])
        if structure == 1:
            msg = f"{g}! {p} {e}"
        elif structure == 2:
            msg = f"{g} {e} {p}. {f}"
        else:
            msg = f"{g}! {p}. {f} {e}"
        pool.add(msg)
    return list(pool)


def send_streak_messages(friends: list[str] | None, message: str, headed: bool) -> None:
    """
    Loads saved state.json, opens TikTok messages page.
    If friends are specified, sends messages to them.
    Otherwise, automatically scans the chat list for all friends with active streaks
    and sends messages to them.
    """
    import os
    
    # Fallback order for loading state:
    # A. MongoDB (most dynamic)
    # B. TIKTOK_STATE_JSON environment variable
    # C. Local state.json file
    state_json_content = load_state_from_db()
    if state_json_content:
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                f.write(state_json_content.strip())
            print("Successfully restored session context from MongoDB.")
        except Exception as err:
            print(f"Warning: Failed to write MongoDB session state to file: {err}")
    else:
        state_json_env = os.getenv("TIKTOK_STATE_JSON")
        if state_json_env:
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(state_json_env.strip())
                print("Successfully restored session context from TIKTOK_STATE_JSON environment variable.")
                # Cache it to MongoDB for subsequent runs
                save_state_to_db(state_json_env.strip())
            except Exception as err:
                print(f"Warning: Failed to restore TIKTOK_STATE_JSON environment variable: {err}")

    if not STATE_FILE.exists():
        print(
            f"Error: No active state found. Please run the script in login mode first:"
        )
        print("  python social_tools/tiktok_streak_keeper.py --login")
        sys.exit(1)

    print(f"\n=== TikTok Streak Keeper: Automation Mode ===")
    if friends:
        print(f"Target friends (explicit list): {', '.join(friends)}")
    else:
        print("Target: All friends with ongoing streaks (Auto-Detect Mode)")
    print(f"Message to send: '{message}'")
    print(f"Browser mode: {'Headed' if headed else 'Headless'}\n")

    with sync_playwright() as p:
        # ── Anti-detection: proxy, user agent, viewport randomization ──
        launch_args = ["--disable-blink-features=AutomationControlled"]
        launch_kwargs = {
            "headless": not headed,
            "args": launch_args,
        }
        # Optional residential proxy via env var (e.g. "http://user:pass@proxy-host:port")
        proxy_url = os.getenv("TIKTOK_PROXY")
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}
            print(f"Using proxy: {proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url}")

        browser = p.chromium.launch(**launch_kwargs)

        viewport = random.choice(_VIEWPORTS)
        user_agent = random.choice(_USER_AGENTS)
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="Asia/Phnom_Penh",
        )
        page = context.new_page()

        # Apply stealth patches if available
        if stealth_sync:
            stealth_sync(page)
            print("Stealth patches applied.")

        try:
            print("Navigating to TikTok Messages...")
            page.goto("https://www.tiktok.com/messages", wait_until="load", timeout=30000)

            # Human-like initial wait (3-7 seconds)
            print("Waiting for page load...")
            _human_delay(page, 3000, 7000)

            # Scroll list container to load all lazy-loaded chats
            try:
                first_item = page.locator('[data-e2e="dm-new-conversation-item"]').first
                first_item.wait_for(state="visible", timeout=10000)
                print("Scrolling chat sidebar to load all conversation items...")
                container = page.evaluate_handle(
                    """() => {
                        const item = document.querySelector('[data-e2e="dm-new-conversation-item"]');
                        if (!item) return null;
                        let parent = item.parentElement;
                        while (parent) {
                            const style = window.getComputedStyle(parent);
                            if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                                return parent;
                            }
                            parent = parent.parentElement;
                        }
                        return null;
                    }"""
                )
                if container.as_element():
                    # Scroll down to lazy-load older chats
                    for _ in range(8):
                        container.as_element().evaluate("el => el.scrollTop += el.clientHeight")
                        _human_delay(page, 600, 1500)
                    # Scroll back to top
                    container.as_element().evaluate("el => el.scrollTop = 0")
                    _human_delay(page, 800, 1800)
                    print("Finished scrolling chat sidebar.")
            except Exception as e:
                print(f"Warning: Failed to scroll chat list: {e}")

            targets = []

            if friends:
                # ── Explicit Friends Mode ──
                for friend in friends:
                    targets.append((None, friend))
            else:
                # ── Auto-Detect Streaks Mode ──
                print("Scanning chat sidebar for ongoing streaks...")

                # ── Auto-Detect Fallback to Hardcoded List ──
                print("Note: TikTok Web does not natively expose streak badges in the DOM.")
                print("Defaulting to your hardcoded list of streak friends from the screenshot:")
                default_friends = [
                    "Ling令",
                    "Estelle",
                    "សមាគមន៍យុវជនប្រឆាំងនឹងសុរ៉ា",
                    "janthedumbie",
                    "tov c ey ✨",
                    "កូនអញកើតម៉ោឪ្យហៅហែងប៉ា",
                    "Hazelnut",
                    "Larry"
                ]
                print(f"Target friends: {', '.join(default_friends)}")
                for friend in default_friends:
                    targets.append((None, friend))

            # Generate pool of 500 alternative messages
            message_pool = generate_streak_message_pool()

            # Send messages to the targeted chats
            for item, name in targets:
                print(f"\nProcessing chat with: '{name}'...")

                # If we don't have the item element yet (Explicit Mode), find and click it
                if item is None:
                    chat_item = page.locator(
                        '[data-e2e="dm-new-conversation-item"], [data-e2e="message-chat-item"], div[class*="ChatItem"], a[href*="/messages"]'
                    ).filter(has_text=name).first

                    if not chat_item.is_visible():
                        chat_item = page.get_by_text(name, exact=False).first

                    if chat_item.is_visible():
                        print(f"Found chat for '{name}'. Clicking to open...")
                        chat_item.click()
                    else:
                        print(f"❌ Error: Could not locate chat item for '{name}' in messages list.")
                        if not headed:
                            page.screenshot(path=str(SCRIPT_DIR / f"failure_{name}.png"))
                        continue
                else:
                    # Auto-Detect Mode: we already have the element, click it directly
                    item.click()

                _human_delay(page, 2000, 5000)  # Wait for chat area to load

                # Locate text box
                text_input = page.locator(
                    '[data-e2e="chat-text-input"], [role="textbox"], div[contenteditable="true"], textarea'
                ).first

                if text_input.is_visible():
                    # Pick a random message from our pool of 500 options if using the default message
                    if message == "Streak!":
                        current_message = random.choice(message_pool)
                    else:
                        current_message = message

                    print(f"Sending message: '{current_message}' to '{name}'...")
                    text_input.click()
                    _human_delay(page, 500, 1500)  # pause before typing
                    text_input.fill(current_message)
                    _human_delay(page, 800, 2000)  # pause before pressing enter
                    text_input.press("Enter")
                    _human_delay(page, 1500, 4000)  # wait for message to register
                    print(f"✅ Message sent successfully to '{name}'!")
                else:
                    print(f"❌ Error: Chat input box not found for '{name}'.")
                    if not headed:
                        page.screenshot(path=str(SCRIPT_DIR / f"failure_input_{name}.png"))

                # Gaussian-distributed delay between friends (mean 45s, range 15-120s)
                if (item, name) != targets[-1]:
                    sleep_seconds = _human_pause_between_friends()
                    print(f"Waiting {sleep_seconds}s before the next friend...")
                    page.wait_for_timeout(sleep_seconds * 1000)

            # Save the updated session state (cookies, local storage) back to state.json and MongoDB
            try:
                context.storage_state(path=STATE_FILE)
                print(f"Updated storage state written to {STATE_FILE}")
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    updated_state = f.read()
                save_state_to_db(updated_state)
            except Exception as e:
                print(f"Warning: Failed to save updated storage state to MongoDB: {e}")

            # ── Check Comment Notifications ──
            try:
                print("\n=== Checking TikTok Comment Notifications ===")
                print("Navigating to TikTok Inbox...")
                page.goto("https://www.tiktok.com/inbox", wait_until="load", timeout=30000)
                _human_delay(page, 3000, 7000)
                
                # Check if the inbox panel is already visible. If not, open it.
                inbox_panel = page.locator('#header-inbox-bar').first
                if not inbox_panel.is_visible():
                    try:
                        inbox_icon = page.locator('div[class*="DivHeaderInboxContainer"], [class*="DivHeaderInboxContainer"], [data-e2e="nav-inbox"], button[aria-label*="Inbox"]').first
                        if inbox_icon.is_visible():
                            print("Inbox dropdown is not visible. Clicking inbox icon in header to open...")
                            inbox_icon.click()
                            _human_delay(page, 2000, 5000)
                    except Exception as click_err:
                        print(f"Warning: Failed to click inbox icon: {click_err}")
                else:
                    print("Inbox dropdown is already open.")

                # Force CSS visibility as a secondary fail-safe fallback
                page.evaluate("""() => {
                    const bar = document.querySelector('#header-inbox-bar');
                    if (!bar) return;
                    let parent = bar.parentElement;
                    while (parent && parent.tagName !== 'BODY') {
                        parent.style.setProperty('display', 'block', 'important');
                        parent.style.setProperty('visibility', 'visible', 'important');
                        parent.style.setProperty('opacity', '1', 'important');
                        parent.style.setProperty('transform', 'none', 'important');
                        parent = parent.parentElement;
                    }
                }""")
                _human_delay(page, 1500, 3000)
                
                # Click Comments tab
                print("Selecting Comments tab...")
                comments_button = page.locator('#inbox-tab-2, button[data-e2e="comments"]').first
                is_selected = comments_button.get_attribute("aria-selected") == "true"
                if not is_selected:
                    if comments_button.is_visible():
                        comments_button.click()
                    else:
                        page.evaluate("""() => {
                            const btn = document.getElementById('inbox-tab-2') || document.querySelector('[data-e2e="comments"]');
                            if (btn) btn.click();
                        }""")
                    _human_delay(page, 3000, 6000)
                else:
                    print("Comments tab is already active.")
                
                # Scroll window to lazy-load older comments (5 scrolls)
                print("Scrolling to load older comments...")
                for i in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    _human_delay(page, 1000, 2500)
                    
                # Extract all comments notifications
                notifications = page.evaluate("""() => {
                    const list = document.querySelector('#header-inbox-list');
                    if (!list) return [];
                    const items = list.querySelectorAll('[data-e2e="inbox-list-item"]');
                    return Array.from(items).map(item => {
                        const titleEl = item.querySelector('[data-e2e="inbox-title"]');
                        const contentEl = item.querySelector('[data-e2e="inbox-content"]');
                        const extraEl = item.querySelector('[class*="StyledExtraText"]');
                        const videoLinkEl = item.querySelector('a:not([href*="/@"]):not([aria-label*="profile"])') || item.querySelector('a[href*="/video/"], a[href*="/photo/"]');
                        
                        const title = titleEl ? (titleEl.textContent || '').trim() : '';
                        const content = contentEl ? (contentEl.textContent || '').trim() : '';
                        const extra = extraEl ? (extraEl.textContent || '').trim() : '';
                        const href = videoLinkEl ? videoLinkEl.getAttribute('href') || '' : '';
                        
                        let text = `${title} ${content}`;
                        if (extra) {
                            text += ` (${extra})`;
                        }
                        
                        return {
                            text: text.replace(/\\s+/g, ' ').trim(),
                            href: href
                        };
                    });
                }""")
                
                # Filter comments and deduplicate
                seen_texts = set()
                comments_list = []
                for n in notifications:
                    text = n['text']
                    href = n['href']
                    if not text:
                        continue
                    lower = text.lower()
                    
                    # Include: commented on, replied, mentioned in comment
                    # Exclude: liked
                    is_comment = ("commented" in lower or "replied" in lower or "mentioned" in lower) and "liked" not in lower
                    if is_comment and text not in seen_texts:
                        seen_texts.add(text)
                        comments_list.append({"text": text, "href": href})
                        
                print(f"Total comments/replies found: {len(comments_list)}")
                
                # Load previously seen comments from MongoDB
                seen_comments_in_db = []
                mongo_uri = os.getenv("MONGODB_URI")
                db_name = os.getenv("DB_NAME", "expTracker")
                if mongo_uri:
                    try:
                        from pymongo import MongoClient
                        client = MongoClient(mongo_uri)
                        db = client[db_name]
                        doc = db["tiktok_settings"].find_one({"key": "seen_comments"})
                        if doc and "value" in doc:
                            seen_comments_in_db = doc["value"]
                    except Exception as e:
                        print(f"Warning: Failed to fetch seen comments from DB: {e}")
                        
                # Identify new comments
                new_comments = []
                for c in comments_list:
                    if c["text"] not in seen_comments_in_db:
                        new_comments.append(c)
                        
                if new_comments:
                    print(f"\nFound {len(new_comments)} NEW comment notifications!")
                    for c in new_comments:
                        print(f"NEW_COMMENT_ALERT: {c['text']} (Link: https://www.tiktok.com{c['href']})")
                    
                    # Update the seen comments in MongoDB
                    all_seen_comments = seen_comments_in_db + [c["text"] for c in new_comments]
                    # Keep max 100 to avoid DB document bloat
                    all_seen_comments = all_seen_comments[-100:]
                    if mongo_uri:
                        try:
                            from pymongo import MongoClient
                            client = MongoClient(mongo_uri)
                            db = client[db_name]
                            db["tiktok_settings"].update_one(
                                {"key": "seen_comments"},
                                {"$set": {"value": all_seen_comments, "updated_at": time.time()}},
                                upsert=True
                            )
                            print("Updated seen comments in MongoDB.")
                        except Exception as e:
                            print(f"Warning: Failed to save seen comments to DB: {e}")
                else:
                    print("No new comment notifications since last run.")
                    
            except Exception as comment_err:
                print(f"Warning: Failed to check comment notifications: {comment_err}")

        except PlaywrightTimeoutError as err:
            print(f"❌ Automation timed out: {err}")
        except Exception as err:
            print(f"❌ An error occurred: {err}")
        finally:
            print("\nClosing browser...")
            browser.close()
            
            # Clean up/delete local state.json file for security
            if STATE_FILE.exists():
                try:
                    STATE_FILE.unlink()
                    print(f"Cleaned up local state file: {STATE_FILE}")
                except Exception as e:
                    print(f"Warning: Failed to delete local state file: {e}")


def main() -> None:
    """
    Entry point to parse arguments and launch correct execution mode.
    """
    parser = argparse.ArgumentParser(
        description="Automate sending direct messages on TikTok to maintain streaks."
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Run script in login mode to authenticate and save session.",
    )
    parser.add_argument(
        "--friend",
        action="append",
        help="Friend's display name or username to message. If omitted, sends to all friends with active streaks.",
    )
    parser.add_argument(
        "--message",
        default="Streak!",
        help="Custom streak message to send (default: 'Streak!').",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run automation browser in headed mode (visible window).",
    )

    args = parser.parse_args()

    if args.login:
        login_mode()
    else:
        send_streak_messages(args.friend, args.message, args.headed)


if __name__ == "__main__":
    main()
