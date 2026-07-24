import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

API_ID = 37786064
API_HASH = "0c5906ff45140b5b9192fe10ffbb6e83"
PHONE = "+855962021314"

async def main():
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    
    if await client.is_user_authorized():
        print("You are already logged in!")
        return
        
    try:
        print("Requesting code...")
        result = await client.send_code_request(PHONE)
        print(f"Code sent successfully!")
        
        # This tells us exactly HOW the code was sent
        print(f"Telegram sent the code via: {type(result.type).__name__}")
        
        if type(result.type).__name__ == 'SentCodeTypeApp':
            print("-> This means it was sent as a message inside your active Telegram app.")
        elif type(result.type).__name__ == 'SentCodeTypeSms':
            print("-> This means it was sent as a regular SMS text message to your phone.")
            
    except FloodWaitError as e:
        print(f"RATE LIMITED: Telegram says we have to wait {e.seconds} seconds before trying again.")
    except Exception as e:
        print(f"ERROR: Failed to send code. Reason: {e}")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
