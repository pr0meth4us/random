#!/usr/bin/env python3
"""
run_scheduler.py
----------------
Continuous scheduler script to run the TikTok Streak Keeper daily at 12:02 AM.
Designed for running inside persistent containers (like on Koyeb).
"""

import os
import sys
import time
import subprocess
from datetime import datetime

# Read configurations from environment variables
FRIENDS_ENV = os.getenv("TIKTOK_FRIENDS", "")
MESSAGE_ENV = os.getenv("TIKTOK_MESSAGE", "Streak!")
RUN_TIME_HOUR = int(os.getenv("SCHEDULE_HOUR", "0"))      # 12 AM (00:00)
RUN_TIME_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "2"))  # 02 minutes (12:02 AM)

if not FRIENDS_ENV:
    print("Error: TIKTOK_FRIENDS environment variable is not set.")
    print("Please set TIKTOK_FRIENDS to a comma-separated list of friend names.")
    sys.exit(1)

FRIENDS = [f.strip() for f in FRIENDS_ENV.split(",") if f.strip()]

print("=== TikTok Streak Keeper Scheduler ===")
print(f"Scheduled Time: {RUN_TIME_HOUR:02d}:{RUN_TIME_MINUTE:02d} daily")
print(f"Friends to message: {', '.join(FRIENDS)}")
print(f"Message: '{MESSAGE_ENV}'\n")

while True:
    now = datetime.now()
    if now.hour == RUN_TIME_HOUR and now.minute == RUN_TIME_MINUTE:
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
        
        # Sleep for 60 seconds to ensure we do not trigger again in the same minute
        time.sleep(60)
    
    # Check every 30 seconds
    time.sleep(30)
