import asyncio
import sys
import getpass
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from _config import API_ID, API_HASH, PHONE

SESSION_PATH = "anon"
HASH_FILE = "/tmp/telegram_phone_code_hash.txt"


async def main():
    if len(sys.argv) != 2:
        print("Usage: complete_login.py <code>")
        return

    code = sys.argv[1]
    with open(HASH_FILE) as f:
        phone_code_hash = f.read().strip()

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    try:
        await client.sign_in(phone=PHONE, code=code, phone_code_hash=phone_code_hash)
        print("LOGIN_OK")
    except SessionPasswordNeededError:
        password = getpass.getpass("Two-step verification password: ")
        await client.sign_in(password=password)
        print("LOGIN_OK")
    except (PhoneCodeInvalidError, PhoneCodeExpiredError) as e:
        print(f"LOGIN_FAILED: {e}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
