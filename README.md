# random

scripts i wrote because i was mildly inconvenienced. nothing serious.

---

- **chat_tools** — turns facebook messenger html exports into something useful
- **image_tools** — makes images smaller
- **gemini_tools** — general Gemini utilities (quick terminal chat, list models)
- **downloaders** — youtube to m4a
- **document_converters** — pdf/excel/txt stuff
- **media_enricher** — looks up movie metadata from tmdb
- **spotify** — dumps your spotify playlists to json
- **json_tools** — prettifies json
- **code_merger** — smashes a whole codebase into one file for LLM context
- **system_tools** — scans bluetooth devices and manages secret/env migrations

---

## setup

```bash
pip install -r requirements.txt
```

copy `.env` and fill in whatever keys the thing you're running needs (`GEMINI_API_KEY`, `MONGODB_URI`, `TMDB_API_KEY`, `SPOTIFY_CLIENT_ID`, etc.)
