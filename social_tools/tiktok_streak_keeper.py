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

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

_VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]


def _human_delay(page, min_ms: int = 800, max_ms: int = 2500):
    page.wait_for_timeout(random.randint(min_ms, max_ms))


def _human_pause_between_friends():
    delay = int(random.gauss(45, 20))
    return max(15, min(delay, 120))


def load_state_from_db() -> str | None:
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


def load_dynamic_config() -> tuple[list[str], dict]:
    """Fetches target friends and message components directly from MongoDB."""
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME", "expTracker")
    friends = []
    components = {}

    if not mongo_uri:
        return friends, components

    try:
        from pymongo import MongoClient
        client = MongoClient(mongo_uri)
        db = client[db_name]

        f_doc = db["tiktok_settings"].find_one({"key": "target_friends"})
        if f_doc and "value" in f_doc:
            friends = f_doc["value"]

        c_doc = db["tiktok_settings"].find_one({"key": "message_components"})
        if c_doc and "value" in c_doc:
            components = c_doc["value"]

    except Exception as e:
        print(f"Warning: Failed to fetch dynamic config from MongoDB: {e}")

    return friends, components


def login_mode() -> None:
    print("\n=== TikTok Streak Keeper: Login Mode ===")
    print("Launching headed browser. Please log into your TikTok account.")
    print("Once logged in, close the browser window or wait 60 seconds to save session.")
    
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

        start_time = time.time()
        try:
            while time.time() - start_time < 60:
                if len(browser.pages) > 0 and not page.is_closed():
                    page.wait_for_timeout(1000)
                else:
                    break
        except Exception:
            pass

        browser.storage_state(path=STATE_FILE)
        print(f"\nStorage state exported successfully to: {STATE_FILE}")
        browser.close()


def generate_streak_message_pool(db_components: dict) -> list[str]:
    """Generates 500 combinations using arrays pulled straight from MongoDB."""
    import random
    
    # Safely pull arrays from DB, with hardcoded fallbacks just in case
    greetings = db_components.get("greetings", ["yo", "ayo", "alov", "weyy", "hey", "oy", "boss", "bro", "heyyy", "sup", "wassup", "wyd"])
    khmer_questions = db_components.get("khmer_questions", ["tver ey nv", "hob bay nv", "reply pg", "tv na td", "rean ot td", "mean ey tmey", "sok te", "muy tv"])
    eng_questions = db_components.get("eng_questions", ["u good?", "wya", "what's good", "u busy?", "how u been", "surviving?"])
    khmer_vibes = db_components.get("khmer_vibes", ["nguy dek hah", "klen kloun", "ot luy te", "la orn", "chher kbal", "busy mles", "boring hah", "jong tv leng"])
    eng_vibes = db_components.get("eng_vibes", ["im ded", "so tired rn", "cant do this rn", "literally me", "bro im sleep", "im dead", "mood"])
    khmer_fillers = db_components.get("khmer_fillers", ["ng eng", "aii", "bat", "ha", "hah", "men ta", "pg", "mles", "der", "nas"])
    eng_fillers = db_components.get("eng_fillers", ["fr", "ngl", "tbh", "lowkey", "highkey", "rn", "bruh", "ong"])
    laughs = db_components.get("laughs", ["xD", "xDD", "lol", "lmao", "lmfao", "haha", "hehe", "wkkw", "crying", ""])
    
    pool = set()
    random_gen = random.Random()
    
    while len(pool) < 500:
        g = random_gen.choice(greetings)
        kq = random_gen.choice(khmer_questions)
        eq = random_gen.choice(eng_questions)
        kv = random_gen.choice(khmer_vibes)
        ev = random_gen.choice(eng_vibes)
        kf = random_gen.choice(khmer_fillers)
        ef = random_gen.choice(eng_fillers)
        l = random_gen.choice(laughs)
        
        template = random_gen.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        
        if template == 1: msg = f"{kq} {ef} {l}"
        elif template == 2: msg = f"{g} {ev} {l}"
        elif template == 3: msg = f"{g} {kv} {kf}"
        elif template == 4: msg = f"{eq} {ef} {l}"
        elif template == 5: msg = f"{ev} {l}"
        elif template == 6: msg = f"{g} {kq} {ef}"
        elif template == 7: msg = f"{ev} {kf} {l}"
        elif template == 8: msg = f"{kv} {ef} {l}"
        elif template == 9: msg = f"{g} {eq}"
        elif template == 10: msg = f"{kq} {l}"
            
        msg = " ".join(msg.split()).strip()
        if msg:
            pool.add(msg)
        
    return list(pool)


def send_streak_messages(cli_friends: list[str] | None, message: str, headed: bool) -> None:
    import os
    
    state_json_content = load_state_from_db()
    if state_json_content:
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                f.write(state_json_content.strip())
            print("Successfully restored session context from MongoDB.")
        except Exception as err:
            pass

    if not STATE_FILE.exists():
        print("Error: No active state found. Please run the script in login mode first.")
        sys.exit(1)

    # Load dynamic config from MongoDB
    db_friends, db_components = load_dynamic_config()

    print(f"\n=== TikTok Streak Keeper: Automation Mode ===")
    print(f"Browser mode: {'Headed' if headed else 'Headless'}\n")

    with sync_playwright() as p:
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--no-sandbox",               # 👈 Critical for Linux Cloud containers
            "--disable-dev-shm-usage",    # 👈 Stops Chrome from crashing due to low RAM
            "--disable-setuid-sandbox",
            "--disable-extensions",       # 👈 Saves memory by turning off extensions
            "--js-flags=--max-old-space-size=256" # 👈 Forces Chrome to use less RAM
        ]
        launch_kwargs = {
            "headless": not headed,
            "args": launch_args,
        }
        
        # Only force the Mac Google Chrome app if we are debugging visibly.
        if headed:
            launch_kwargs["channel"] = "chrome"
        
        browser = p.chromium.launch(**launch_kwargs)

        viewport = {"width": 1280, "height": 800}
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="Asia/Phnom_Penh",
        )
        page = context.new_page()

        if stealth_sync:
            stealth_sync(page)

        try:
            def _take_screenshot(step_name: str):
                ss_path = os.path.abspath(f"tiktok_debug_{step_name}.png")
                try:
                    page.screenshot(path=ss_path)
                    print(f"SCREENSHOT_SAVED:{ss_path}")
                except Exception as e:
                    print(f"Warning: Failed to capture screenshot {step_name}: {e}")

            # Aggressively spoof Mac fingerprint to match the User-Agent
            page.add_init_script("""
                Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
                Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
                Object.defineProperty(navigator, 'oscpu', { get: () => 'Intel Mac OS X 10_15_7' });
                
                // Overwrite webdriver
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                
                // Spoof plugins to look like a real Chrome browser
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5] // Just needs to have length > 0
                });
            """)

            print("Navigating to TikTok Messages...")
            page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=30000)
            _human_delay(page, 5000, 8000)
            
            # Print page title and length of HTML to see if we got blocked
            html_content = page.content()
            print(f"DEBUG: Page Title = '{page.title()}'")
            print(f"DEBUG: HTML Content Length = {len(html_content)} bytes")
            if len(html_content) < 1000:
                print(f"DEBUG: HTML Content snippet = {html_content[:500]}")
                
            # Save HTML to a file for Telegram delivery
            html_path = os.path.abspath("tiktok_debug.html")
            try:
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"HTML_SAVED:{html_path}")
            except Exception as e:
                print(f"Warning: Failed to save HTML dump: {e}")
            
            _take_screenshot("1_initial_load")

            try:
                first_item = page.locator('[data-e2e="dm-new-conversation-item"]').first
                first_item.wait_for(state="visible", timeout=10000)
                container = page.evaluate_handle(
                    """() => {
                        const item = document.querySelector('[data-e2e="dm-new-conversation-item"]');
                        if (!item) return null;
                        let parent = item.parentElement;
                        while (parent) {
                            const style = window.getComputedStyle(parent);
                            if (style.overflowY === 'auto' || style.overflowY === 'scroll') return parent;
                            parent = parent.parentElement;
                        }
                        return null;
                    }"""
                )
                if container.as_element():
                    for _ in range(8):
                        container.as_element().evaluate("el => el.scrollTop += el.clientHeight")
                        _human_delay(page, 600, 1500)
                    container.as_element().evaluate("el => el.scrollTop = 0")
                    _human_delay(page, 800, 1800)
                    _take_screenshot("2_after_scrolling")
            except Exception:
                pass

            targets = []
            if cli_friends:
                print(f"Target friends (CLI override): {', '.join(cli_friends)}")
                for friend in cli_friends:
                    targets.append((None, friend))
            elif db_friends:
                print(f"Target friends (Loaded from MongoDB): {', '.join(db_friends)}")
                for friend in db_friends:
                    targets.append((None, friend))
            else:
                print("Target friends (Hardcoded fallback): Ling令, Estelle, etc...")
                fallback_friends = ["Ling令", "Estelle", "សមាគមន៍យុវជនប្រឆាំងនឹងសុរ៉ា", "janthedumbie", "tov c ey ✨", "កូនអញកើតម៉ោឪ្យហៅហែងប៉ា", "Hazelnut", "Larry"]
                for friend in fallback_friends:
                    targets.append((None, friend))

            # Randomize the sending order
            random.shuffle(targets)

            # Generate messages using MongoDB components
            message_pool = generate_streak_message_pool(db_components)

            for item, name in targets:
                print(f"\nProcessing chat with: '{name}'...")

                if item is None:
                    chat_item = page.locator(
                        '[data-e2e="dm-new-conversation-item"], [data-e2e="message-chat-item"], div[class*="ChatItem"], a[href*="/messages"]'
                    ).filter(has_text=name).first

                    if not chat_item.is_visible():
                        chat_item = page.get_by_text(name, exact=False).first

                    if chat_item.is_visible():
                        chat_item.click()
                    else:
                        print(f"❌ Error: Could not locate chat item for '{name}'.")
                        _take_screenshot(f"error_locating_chat_{name}")
                        continue
                else:
                    item.click()

                _human_delay(page, 2000, 5000)

                text_input = page.locator(
                    '[data-e2e="chat-text-input"], [role="textbox"], div[contenteditable="true"], textarea'
                ).first

                if text_input.is_visible():
                    if message == "Streak!":
                        current_message = random.choice(message_pool)
                    else:
                        current_message = message

                    print(f"Sending message: '{current_message}' to '{name}'...")
                    text_input.click()
                    _human_delay(page, 500, 1500)
                    
                    keystroke_delay = random.randint(40, 110)
                    text_input.press_sequentially(current_message, delay=keystroke_delay)
                    
                    _human_delay(page, 800, 2000)
                    text_input.press("Enter")
                    _human_delay(page, 1500, 4000)
                    print(f"✅ Message sent successfully to '{name}'!")
                else:
                    print(f"❌ Error: Chat input box not found for '{name}'.")

                if (item, name) != targets[-1]:
                    sleep_seconds = _human_pause_between_friends()
                    print(f"Waiting {sleep_seconds}s before the next friend...")
                    page.wait_for_timeout(sleep_seconds * 1000)

            try:
                context.storage_state(path=STATE_FILE)
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    updated_state = f.read()
                save_state_to_db(updated_state)
            except Exception:
                pass

            # Inbox Notifications Parsing Block
            try:
                print("\n=== Checking TikTok Comment Notifications ===")
                page.goto("https://www.tiktok.com/inbox", wait_until="load", timeout=30000)
                _human_delay(page, 3000, 7000)
                
                inbox_panel = page.locator('#header-inbox-bar').first
                if not inbox_panel.is_visible():
                    try:
                        inbox_icon = page.locator('div[class*="DivHeaderInboxContainer"], [data-e2e="nav-inbox"]').first
                        if inbox_icon.is_visible():
                            inbox_icon.click()
                            _human_delay(page, 2000, 5000)
                    except Exception:
                        pass

                comments_button = page.locator('#inbox-tab-2, button[data-e2e="comments"]').first
                is_selected = comments_button.get_attribute("aria-selected") == "true"
                if not is_selected and comments_button.is_visible():
                    comments_button.click()
                    _human_delay(page, 3000, 6000)
                
                for i in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    _human_delay(page, 1000, 2500)
                    
                notifications = page.evaluate("""() => {
                    const list = document.querySelector('#header-inbox-list');
                    if (!list) return [];
                    const items = list.querySelectorAll('[data-e2e="inbox-list-item"]');
                    return Array.from(items).map(item => {
                        const titleEl = item.querySelector('[data-e2e="inbox-title"]');
                        const contentEl = item.querySelector('[data-e2e="inbox-content"]');
                        const extraEl = item.querySelector('[class*="StyledExtraText"]');
                        const videoLinkEl = item.querySelector('a:not([href*="/@"]):not([aria-label*="profile"])');
                        const title = titleEl ? (titleEl.textContent || '').trim() : '';
                        const content = contentEl ? (contentEl.textContent || '').trim() : '';
                        const extra = extraEl ? (extraEl.textContent || '').trim() : '';
                        const href = videoLinkEl ? videoLinkEl.getAttribute('href') || '' : '';
                        let text = `${title} ${content}`;
                        if (extra) text += ` (${extra})`;
                        return { text: text.replace(/\\s+/g, ' ').trim(), href: href };
                    });
                }""")
                
                seen_texts = set()
                comments_list = []
                for n in notifications:
                    text = n['text']
                    href = n['href']
                    if not text: continue
                    lower = text.lower()
                    is_comment = ("commented" in lower or "replied" in lower or "mentioned" in lower) and "liked" not in lower
                    if is_comment and text not in seen_texts:
                        seen_texts.add(text)
                        comments_list.append({"text": text, "href": href})
                        
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
                    except Exception:
                        pass
                        
                new_comments = [c for c in comments_list if c["text"] not in seen_comments_in_db]
                        
                if new_comments:
                    print(f"\nFound {len(new_comments)} NEW comment notifications!")
                    for c in new_comments:
                        print(f"NEW_COMMENT_ALERT: {c['text']} (Link: https://www.tiktok.com{c['href']})")
                    all_seen_comments = seen_comments_in_db + [c["text"] for c in new_comments]
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
                        except Exception:
                            pass
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
            if STATE_FILE.exists():
                try:
                    STATE_FILE.unlink()
                except Exception:
                    pass

def main() -> None:
    parser = argparse.ArgumentParser(description="Automate sending direct messages on TikTok.")
    parser.add_argument("--login", action="store_true", help="Run script in login mode.")
    parser.add_argument("--friend", action="append", help="Friend's display name to message. Overrides MongoDB.")
    parser.add_argument("--message", default="Streak!", help="Custom message (default triggers dynamic pool).")
    parser.add_argument("--headed", action="store_true", help="Run browser visibly.")
    args = parser.parse_args()

    if args.login:
        login_mode()
    else:
        send_streak_messages(args.friend, args.message, args.headed)

if __name__ == "__main__":
    main()
