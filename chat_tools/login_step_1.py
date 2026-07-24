import asyncio
from telethon import TelegramClient

API_ID = 37786064
API_HASH = "0c5906ff45140b5b9192fe10ffbb6e83"
PHONE = "+855962021314"

async def main():
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        # This will send the login code to your Telegram app
        await client.send_code_request(PHONE)
        print("Code requested successfully!")
    else:
        print("Already authorized!")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
