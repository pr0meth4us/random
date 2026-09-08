# Mac Cleaner

A local storage cleaner: scan caches and junk, browse what is using space, find
duplicates and large files, and move the selected items to the Trash.

## Running it

```bash
# Backend — binds to 127.0.0.1:8000
cd backend
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

## Safety model

The backend can move a user's files, so it is deliberately constrained.

**Nothing is deleted.** Removal goes through the macOS Trash API
(`send2trash`), so every item stays restorable from the Trash.

**Only local callers.** The server binds to loopback, accepts requests from
local dev origins only, and rejects any request whose `Host` header is not
loopback — otherwise a hostile page could point a domain it controls at
`127.0.0.1` and drive the API from the browser. The frontend talks to
`127.0.0.1` rather than `localhost`, since `localhost` may resolve to `::1`
first.

**Paths are checked, not trusted.** Every inbound path is expanded and fully
resolved — symlinks included — *before* it is checked, so a symlink out of the
home directory cannot be used to escape the allow-list.

- Readable: the home directory, `/Applications`, `/Library/Caches`.
- Removable: inside the home directory only, minus two deny-lists —
  structural directories that may be emptied but never removed (`~`,
  `~/Library`, `~/Documents`, `~/Library/Caches`, …), and subtrees that are
  never touched at all: credentials (`~/.ssh`, `~/.gnupg`, `~/.aws`,
  `~/.config`), keychains, application support and container state, and
  `~/Library/Mobile Documents` — deleting in the iCloud mirror deletes from
  every one of the user's devices.

**Refusals are reported, not silent.** A refused path comes back in the
response with a reason. Validation runs before nested paths are collapsed, so a
refused parent cannot silently swallow the permitted children selected with it.
`POST /api/clean` also accepts `{"dry_run": true}` to preview exactly what would
move.

**Only regenerable caches are bulk-selectable.** Each category carries a `safe`
flag; personal folders (Documents, Downloads, Applications) are shown for
context but never pre-checked.

## Build Artifacts

Dependency and build folders (`node_modules`, `.venv`, `target`, `.next`, …)
are usually the largest reclaimable thing on a developer's machine, and they
sit in project folders rather than in any cache directory.

Ambiguity is handled with markers rather than name matching alone: a folder
called `build` or `dist` may well be hand-written source, so most kinds are
only reported when something proves what produced them — `package.json` beside
`node_modules`, `pyvenv.cfg` inside `.venv`, `Cargo.toml` beside `target`. An
unmarked candidate is left alone. `.git` is never entered.

A matched folder is not descended into, so a nested `node_modules` counts once,
inside its parent. Nothing here is ever bulk-selected: these regenerate, but
regenerating costs an install or a compile, and only you know whether that is
convenient right now.

## Layout

| File | Role |
| --- | --- |
| `backend/safety.py` | Path rules and the category list. No web dependencies. |
| `backend/scanner.py` | Filesystem measurement: sizes, duplicates, large files. |
| `backend/main.py` | FastAPI endpoints — transport only. |
| `backend/test_backend.py` | Tests for the above two modules. |

## Tests

Stdlib only, no server or install required:

```bash
cd backend && python3 -m unittest test_backend -v
```
