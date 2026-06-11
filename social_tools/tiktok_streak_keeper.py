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

SCRIPT_DIR = Path(__file__).resolve().parent
SESSION_DIR = SCRIPT_DIR / "tiktok_session"


def login_mode() -> None:
    """
    Launches Chrome in headed mode so the user can log in manually
    and saves the session context.
    """
    print("\n=== TikTok Streak Keeper: Login Mode ===")
    print("Launching headed browser. Please log into your TikTok account.")
    print("Once logged in, close the browser window or wait 60 seconds to save session.")
    print(f"Session data will be stored in: {SESSION_DIR}\n")

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
        while time.time() - start_time < 60:
            if browser.is_connected() and len(browser.pages) > 0:
                time.sleep(1)
            else:
                break

        print("\nSession saved successfully. You can now run the script in automation mode.")
        browser.close()


def send_streak_messages(friends: list[str], message: str, headed: bool) -> None:
    """
    Loads saved session state, opens TikTok messages page, selects
    each specified friend, and sends the streak message.
    """
    if not SESSION_DIR.exists() or not any(SESSION_DIR.iterdir()):
        print(
            "Error: No active session found. Please run the script in login mode first:"
        )
        print("  python social_tools/tiktok_streak_keeper.py --login")
        sys.exit(1)

    print(f"\n=== TikTok Streak Keeper: Automation Mode ===")
    print(f"Friends to contact: {', '.join(friends)}")
    print(f"Message to send: '{message}'")
    print(f"Browser mode: {'Headed' if headed else 'Headless'}\n")

    with sync_playwright() as p:
        # Launch Chromium with persistent context to load saved session
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=not headed,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = browser.pages[0]

        try:
            print("Navigating to TikTok Messages...")
            page.goto("https://www.tiktok.com/messages", wait_until="load", timeout=30000)

            # Wait for messages page structure to load
            print("Waiting for page load...")
            page.wait_for_timeout(5000)  # Give it a few seconds to load completely

            for friend in friends:
                print(f"\nLooking for chat with: '{friend}'...")

                # Look for a chat list item containing friend's name (case-insensitive text match)
                chat_item = page.locator(
                    'div[class*="ChatItem"], [data-e2e*="chat-item"], a[href*="/messages"]'
                ).filter(has_text=friend).first

                if not chat_item.is_visible():
                    # Fallback locator: check standard text elements containing friend name
                    chat_item = page.get_by_text(friend, exact=False).first

                if chat_item.is_visible():
                    print(f"Found chat for '{friend}'. Clicking to open...")
                    chat_item.click()
                    page.wait_for_timeout(2000)  # Wait for chat area to load

                    # Locate text box
                    text_input = page.locator(
                        '[data-e2e="chat-text-input"], [role="textbox"], div[contenteditable="true"], textarea'
                    ).first

                    if text_input.is_visible():
                        print(f"Sending message: '{message}' to '{friend}'...")
                        text_input.click()
                        text_input.fill(message)
                        page.wait_for_timeout(1000)
                        text_input.press("Enter")
                        page.wait_for_timeout(2000)  # Wait for message to register
                        print(f"✅ Message sent to '{friend}'!")
                    else:
                        print(f"❌ Error: Chat input box not found for '{friend}'.")
                else:
                    print(f"❌ Error: Could not locate chat item for '{friend}' in messages list.")
                    # Take screenshot for debugging if running headless
                    if not headed:
                        screenshot_path = SCRIPT_DIR / f"failure_{friend}.png"
                        page.screenshot(path=str(screenshot_path))
                        print(f"Screenshot saved for debugging: {screenshot_path}")

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
        help="Friend's display name or username to message. Can be specified multiple times.",
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
        if not args.friend:
            print("Error: Please specify at least one friend with --friend.")
            print("Example: python social_tools/tiktok_streak_keeper.py --friend 'Friend Name'")
            sys.exit(1)
        send_streak_messages(args.friend, args.message, args.headed)


if __name__ == "__main__":
    main()
