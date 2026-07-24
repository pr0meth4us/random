import asyncio
import qrcode
import getpass
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 37786064
API_HASH = "0c5906ff45140b5b9192fe10ffbb6e83"

async def main():
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Generating QR code for login...")
        qr_login = await client.qr_login()
        
        print("\n=== NO CODE NEEDED! ===")
        print("Please scan the QR code below with your Telegram App:")
        print("1. Open Telegram on your phone")
        print("2. Go to Settings -> Devices -> Link Desktop Device")
        print("3. Point your camera at this QR code")
        print("========================\n")
        
        qr = qrcode.QRCode()
        qr.add_data(qr_login.url)
        qr.print_ascii()
        
        print("\nWaiting for you to scan... (Timeout in 2 minutes)")
        
        try:
            await qr_login.wait(timeout=120)
            print("Logged in successfully via QR code!")
        except SessionPasswordNeededError:
            print("\n*** Two-step verification is enabled on your account! ***")
            password = getpass.getpass("Please enter your Telegram cloud password: ")
            await client.sign_in(password=password)
            print("Logged in successfully with password!")
        except Exception as e:
            print(f"Failed to log in: {e}")
    else:
        print("You are already logged in!")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
