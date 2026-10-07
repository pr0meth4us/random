import asyncio
import getpass
from telethon import TelegramClient
from _config import API_ID, API_HASH

SESSION_PATH = "anon"


async def main():
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        print("LOGIN_OK: already authorized")
        await client.disconnect()
        return

    password = getpass.getpass("Two-step verification password: ")
    await client.sign_in(password=password)
    print("LOGIN_OK")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
