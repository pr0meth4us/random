#!/usr/bin/env python3
"""
run_scheduler.py
----------------
Continuous scheduler script to run the TikTok Streak Keeper daily.
Designed for running inside persistent containers (like on Koyeb).

Streaks reset at midnight, so this runs at ~11:00 PM + random jitter (0-20 min)
to ensure all friends get messaged before the day rolls over.
Worst case timing: 11:20 PM start + 8 friends * ~120s max delay = ~11:36 PM. Safe.
"""

import os
import sys
import time
import random
import subprocess
from datetime import datetime

# Read configurations from environment variables
FRIENDS_ENV = os.getenv("TIKTOK_FRIENDS", "")
MESSAGE_ENV = os.getenv("TIKTOK_MESSAGE", "Streak!")
RUN_TIME_HOUR = int(os.getenv("SCHEDULE_HOUR", "23"))     # 11 PM — gives ~1 hour buffer before midnight reset
RUN_TIME_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))   # base minute (jitter added on top)

FRIENDS = [f.strip() for f in FRIENDS_ENV.split(",") if f.strip()] if FRIENDS_ENV else []

print("=== TikTok Streak Keeper Scheduler ===")
print(f"Scheduled Base Time: {RUN_TIME_HOUR:02d}:{RUN_TIME_MINUTE:02d} daily + random 0-20 min jitter")
if FRIENDS:
    print(f"Friends to message: {', '.join(FRIENDS)}")
else:
    print("Friends: Auto-detecting all active streaks in the sidebar")
print(f"Message: '{MESSAGE_ENV}'\n")

already_ran_today = None  # Track which date we last ran on

while True:
    now = datetime.now()
    today = now.date()

    # Only run once per day
    if already_ran_today == today:
        time.sleep(30)
        continue

    # Check if we've reached the scheduled hour
    if now.hour == RUN_TIME_HOUR and now.minute >= RUN_TIME_MINUTE:
        # Add random jitter (0-20 minutes) — but only wait once at the trigger point
        jitter_seconds = random.randint(0, 20 * 60)
        jitter_min = jitter_seconds // 60
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Schedule triggered. Adding {jitter_min}m jitter before executing...")
        time.sleep(jitter_seconds)

        now = datetime.now()
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Triggering TikTok Streak Keeper...")

        # Build command arguments
        cmd = ["python3", "social_tools/tiktok_streak_keeper.py"]
        for friend in FRIENDS:
            cmd.extend(["--friend", friend])
        cmd.extend(["--message", MESSAGE_ENV])

        try:
            # Execute the automation script
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print("=== Output ===")
            print(result.stdout)
            print("==============")
            print("✅ Daily streak check completed.")
        except subprocess.CalledProcessError as err:
            print(f"❌ Error during streak keeper run (exit code {err.returncode}):")
            print(err.stderr or err.stdout)

        already_ran_today = today

    # Check every 30 seconds
    time.sleep(30)
