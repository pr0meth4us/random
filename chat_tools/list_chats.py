import asyncio
from telethon import TelegramClient

API_ID = 37786064
API_HASH = "0c5906ff45140b5b9192fe10ffbb6e83"

async def main():
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    
    print("Searching ALL chats for 'som' or 'viseth'...")
    print("-" * 30)
    
    count = 0
    async for dialog in client.iter_dialogs():
        name = dialog.name or ""
        lower_name = name.lower()
        if "som" in lower_name or "viseth" in lower_name:
            print(f"Match found: '{name}'")
            count += 1
            
    if count == 0:
        print("No matches found in any of your chats.")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
