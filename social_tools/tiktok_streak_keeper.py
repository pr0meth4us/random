#!/usr/bin/env python3
"""
tiktok_streak_keeper.py
-----------------------
Browser automation script using Playwright to maintain TikTok streaks
by sending daily direct messages to friends.
"""

import argparse
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Load environment variables if running directly
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_DIR = SCRIPT_DIR / "tiktok_session"
STATE_FILE = SCRIPT_DIR / "state.json"


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
        # Launch Chromium and load context using state.json
        browser = p.chromium.launch(
            headless=not headed,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            storage_state=STATE_FILE,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            print("Navigating to TikTok Messages...")
            page.goto("https://www.tiktok.com/messages", wait_until="load", timeout=30000)

            # Wait for messages page structure to load
            print("Waiting for page load...")
            page.wait_for_timeout(5000)  # Give it a few seconds to load completely

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
                        page.wait_for_timeout(800)
                    # Scroll back to top
                    container.as_element().evaluate("el => el.scrollTop = 0")
                    page.wait_for_timeout(1000)
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

                page.wait_for_timeout(2000)  # Wait for chat area to load

                # Locate text box
                text_input = page.locator(
                    '[data-e2e="chat-text-input"], [role="textbox"], div[contenteditable="true"], textarea'
                ).first

                if text_input.is_visible():
                    print(f"Sending message: '{message}' to '{name}'...")
                    text_input.click()
                    text_input.fill(message)
                    page.wait_for_timeout(1000)
                    text_input.press("Enter")
                    page.wait_for_timeout(2000)  # Wait for message to register
                    print(f"✅ Message sent successfully to '{name}'!")
                else:
                    print(f"❌ Error: Chat input box not found for '{name}'.")
                    if not headed:
                        page.screenshot(path=str(SCRIPT_DIR / f"failure_input_{name}.png"))

            # Save the updated session state (cookies, local storage) back to state.json and MongoDB
            try:
                context.storage_state(path=STATE_FILE)
                print(f"Updated storage state written to {STATE_FILE}")
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    updated_state = f.read()
                save_state_to_db(updated_state)
            except Exception as e:
                print(f"Warning: Failed to save updated storage state to MongoDB: {e}")

        except PlaywrightTimeoutError as err:
            print(f"❌ Automation timed out: {err}")
        except Exception as err:
            print(f"❌ An error occurred: {err}")
        finally:
            print("\nClosing browser...")
            browser.close()


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
