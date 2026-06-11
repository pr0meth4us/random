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
        try:
            while time.time() - start_time < 60:
                if len(browser.pages) > 0 and not page.is_closed():
                    page.wait_for_timeout(1000)
                else:
                    break
        except Exception:
            pass

        print("\nSession saved successfully. You can now run the script in automation mode.")
        browser.close()


def send_streak_messages(friends: list[str] | None, message: str, headed: bool) -> None:
    """
    Loads saved session state, opens TikTok messages page.
    If friends are specified, sends messages to them.
    Otherwise, automatically scans the chat list for all friends with active streaks
    and sends messages to them.
    """
    if not SESSION_DIR.exists() or not any(SESSION_DIR.iterdir()):
        print(
            "Error: No active session found. Please run the script in login mode first:"
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

            targets = []

            if friends:
                # ── Explicit Friends Mode ──
                for friend in friends:
                    targets.append((None, friend))
            else:
                # ── Auto-Detect Streaks Mode ──
                print("Scanning chat sidebar for ongoing streaks...")

                # Scroll the sidebar slightly to trigger lazy-loaded elements
                sidebar = page.locator('div[class*="ChatList"], [data-e2e="chat-list"], div[class*="Sidebar"]').first
                if sidebar.is_visible():
                    sidebar.evaluate("element => element.scrollTop = 400")
                    page.wait_for_timeout(1000)
                    sidebar.evaluate("element => element.scrollTop = 0")
                    page.wait_for_timeout(1000)

                # Locate all chat items
                chat_items_locator = page.locator(
                    '[data-e2e="dm-new-conversation-item"], [data-e2e="message-chat-item"], div[class*="ChatItem"], a[href*="/messages"]'
                )

                try:
                    chat_items_locator.first.wait_for(timeout=10000)
                except Exception:
                    print("Warning: Could not locate chat items sidebar. Is the screen size too small or session expired?")

                chat_items = chat_items_locator.all()
                print(f"Found {len(chat_items)} total chats in sidebar. Checking for streak badges...")

                for item in chat_items:
                    has_streak = False

                    # Check for fire emoji in the text
                    try:
                        text_content = item.inner_text()
                        if "🔥" in text_content:
                            has_streak = True
                    except Exception:
                        pass

                    if not has_streak:
                        # Common selectors or attributes associated with streak flame/combo/badges
                        streak_selectors = [
                            '[data-e2e*="streak"]', '[class*="streak"]', '[class*="Streak"]',
                            '[class*="flame"]', '[class*="Flame"]', '[class*="fire"]', '[class*="Fire"]',
                            '[class*="combo"]', '[class*="Combo"]', 'img[alt*="streak" i]', 'svg[class*="streak" i]'
                        ]
                        for selector in streak_selectors:
                            try:
                                if item.locator(selector).first.is_visible():
                                    has_streak = True
                                    break
                            except Exception:
                                continue

                    if has_streak:
                        # Extract the friend's name from text inside the chat item
                        name_element = item.locator('[data-e2e="dm-new-conversation-nickname"], p[class*="Name"], div[class*="Name"], span[class*="Name"], h4, h5').first
                        if name_element.is_visible():
                            name = name_element.inner_text().strip()
                        else:
                            all_text = item.inner_text().strip()
                            name = all_text.split('\n')[0] if all_text else "Unknown Friend"

                        print(f"Found active streak with: '{name}'")
                        targets.append((item, name))

                if not targets:
                    print("No active streaks detected in the sidebar.")

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
