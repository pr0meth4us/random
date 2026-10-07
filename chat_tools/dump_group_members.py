"""Dump a Telegram group's members to TSV/JSON.

    python dump_group_members.py <chat-name-substring> [--out members.tsv] [--json]
    python dump_group_members.py --list            # show groups you're in

Prints: id, display name, username, phone (when visible to you).
Read-only: joins nothing, sends nothing, changes nothing.
"""
import asyncio, sys, json, csv
from telethon import TelegramClient
from _config import API_ID, API_HASH


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = None
    if '--out' in sys.argv:
        out = sys.argv[sys.argv.index('--out') + 1]
        args = [a for a in args if a != out]
    as_json = '--json' in sys.argv

    client = TelegramClient('anon', API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        print('NOT AUTHORIZED — run qr_login.py first'); return

    if '--list' in sys.argv or not args:
        async for d in client.iter_dialogs():
            if d.is_group or d.is_channel:
                print(f'{d.id}\t{d.name}')
        await client.disconnect(); return

    query = args[0].lower()
    target = None
    async for d in client.iter_dialogs():
        if (d.is_group or d.is_channel) and query in (d.name or '').lower():
            target = d; break
    if target is None:
        print(f'No group matching {args[0]!r}'); await client.disconnect(); return

    print(f'group: {target.name}  (id {target.id})', file=sys.stderr)
    rows = []
    async for u in client.iter_participants(target):
        name = ' '.join(p for p in (u.first_name, u.last_name) if p) or ''
        rows.append({'id': u.id, 'name': name.strip(),
                     'username': u.username or '', 'phone': u.phone or '',
                     'bot': bool(u.bot)})
    rows = [r for r in rows if not r['bot']]
    print(f'members (excluding bots): {len(rows)}', file=sys.stderr)

    if as_json:
        text = json.dumps(rows, ensure_ascii=False, indent=2)
        (open(out, 'w').write(text) if out else print(text))
    else:
        f = open(out, 'w', newline='') if out else sys.stdout
        w = csv.DictWriter(f, fieldnames=['id', 'name', 'username', 'phone'],
                           delimiter='\t', extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
        if out: f.close()
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
