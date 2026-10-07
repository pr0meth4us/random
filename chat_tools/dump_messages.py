"""Dump recent messages from a Telegram chat or channel.

    python dump_messages.py <chat-name-substring> [--limit 50] [--json out.json]

Read-only: sends nothing, joins nothing, marks nothing read.
"""
import asyncio, sys, json
from telethon import TelegramClient
from _config import API_ID, API_HASH


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    limit = 50
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
        args = [a for a in args if a != str(limit)]
    out = None
    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        args = [a for a in args if a != out]
    if not args:
        print(__doc__); return

    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print('NOT AUTHORIZED'); return

    query = args[0].lower()
    target = None
    async for d in client.iter_dialogs():
        if query in (d.name or '').lower():
            target = d; break
    if target is None:
        print(f'no chat matching {args[0]!r}'); await client.disconnect(); return

    print(f'chat: {target.name}', file=sys.stderr)
    msgs = []
    async for m in client.iter_messages(target, limit=limit):
        if not (m.text or '').strip():
            continue
        msgs.append({'id': m.id,
                     'date': m.date.isoformat() if m.date else None,
                     'views': getattr(m, 'views', None),
                     'text': m.text})
    if out:
        json.dump(msgs, open(out, 'w'), ensure_ascii=False, indent=1)
        print(f'{len(msgs)} messages -> {out}', file=sys.stderr)
    else:
        for m in msgs:
            print(f"--- {m['date']}  views={m['views']}")
            print(m['text'][:1500]); print()
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
