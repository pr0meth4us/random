import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from _config import API_ID, API_HASH, PHONE

SESSION_PATH = "anon"
HASH_FILE = "/tmp/telegram_phone_code_hash.txt"


async def main():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        print("LOGIN_OK: already authorized")
        await client.disconnect()
        return

    try:
        result = await client.send_code_request(PHONE)
        with open(HASH_FILE, "w") as f:
            f.write(result.phone_code_hash)
        kind = type(result.type).__name__
        print(f"CODE_SENT via {kind} to {PHONE}")
    except FloodWaitError as e:
        print(f"RATE_LIMITED: wait {e.seconds}s before retrying")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
