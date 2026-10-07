import asyncio
import time
import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from _config import API_ID, API_HASH

QR_IMAGE_PATH = "/tmp/telegram_login_qr.png"
TOTAL_TIMEOUT = 300


async def main():
    client = TelegramClient("anon", API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        print("LOGIN_OK: already authorized")
        await client.disconnect()
        return

    deadline = time.monotonic() + TOTAL_TIMEOUT
    qr_login = await client.qr_login()
    qrcode.make(qr_login.url).save(QR_IMAGE_PATH)
    print(f"QR_READY: {QR_IMAGE_PATH}")

    while time.monotonic() < deadline:
        try:
            await qr_login.wait(timeout=20)
            print("LOGIN_OK: scanned")
            break
        except SessionPasswordNeededError:
            print("LOGIN_NEEDS_PASSWORD: two-step verification is enabled, can't proceed headlessly")
            break
        except asyncio.TimeoutError:
            await qr_login.recreate()
            qrcode.make(qr_login.url).save(QR_IMAGE_PATH)
            continue
    else:
        print("LOGIN_TIMEOUT: no scan within window")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
