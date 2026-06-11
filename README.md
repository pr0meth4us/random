# random

scripts i wrote because i was mildly inconvenienced. nothing serious.

---

- **social_tools** — tiktok bot that texts people so i don't have to
- **chat_tools** — turns facebook messenger html exports into something useful
- **ocr_tools** — reads khmer text from images, asks gemini what it means
- **image_tools** — makes images smaller
- **downloaders** — youtube to m4a
- **document_converters** — pdf/excel/txt stuff
- **media_enricher** — looks up movie metadata from tmdb
- **spotify** — dumps your spotify playlists to json
- **json_tools** — prettifies json
- **code_merger** — smashes a whole codebase into one file for LLM context
- **system_tools** — scans bluetooth devices. ran it once.
- **spot_the_difference** — opencv thing that finds differences between two images

---

## setup

```bash
pip install -r requirements.txt
playwright install chromium  # only if you're using the tiktok thing
```

copy `.env` and fill in whatever keys the thing you're running needs (`GEMINI_API_KEY`, `MONGODB_URI`, `TMDB_API_KEY`, `SPOTIFY_CLIENT_ID`, etc.)
