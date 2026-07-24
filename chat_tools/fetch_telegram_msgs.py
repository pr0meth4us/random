import json
import asyncio
import os
from telethon import TelegramClient

API_ID = 37786064
API_HASH = "0c5906ff45140b5b9192fe10ffbb6e83"

TARGET_CHAT = "Visethvathanak Som"
OUTPUT_FILE = "telegram_messages.json"
VOICE_DIR = "voice_messages"
LIMIT = 100

async def main():
    print("Starting client. If you aren't logged in, it will ask for your phone number and code.")
    client = TelegramClient('anon', API_ID, API_HASH)
    await client.start()
    
    print("Searching for the chat...")
    target_entity = None
    
    async for dialog in client.iter_dialogs():
        name = dialog.name or ""
        if TARGET_CHAT.lower() in name.lower():
            target_entity = dialog.entity
            print(f"Found chat: {name}")
            break
            
    if not target_entity:
        print(f"Could not find a chat matching '{TARGET_CHAT}'.")
        return

    # Create directory for voice messages if it doesn't exist
    os.makedirs(VOICE_DIR, exist_ok=True)

    print(f"Fetching last {LIMIT} messages...")
    messages = []
    
    async for message in client.iter_messages(target_entity, limit=LIMIT):
        msg_data = {
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "text": message.text,
            "sender_id": message.sender_id,
            "voice_file": None
        }
        
        # Download if it is a voice message
        if getattr(message, 'voice', None):
            print(f"Downloading voice message {message.id}...")
            # We save it with .ogg extension since Telegram voice notes are OGG Opus
            file_path = await client.download_media(message, file=os.path.join(VOICE_DIR, f"voice_{message.id}.ogg"))
            msg_data["voice_file"] = file_path

        messages.append(msg_data)
        
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully saved {len(messages)} messages to {OUTPUT_FILE}")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
