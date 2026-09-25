import asyncio
from telethon import TelegramClient
from _config import API_ID, API_HASH, PHONE

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
