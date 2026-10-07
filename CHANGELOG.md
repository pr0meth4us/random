## [2026-10-07] - Keep personal media out of the repo
- chore: `.gitignore` now excludes recordings (`*.m4a`), transcripts, generated `.docx`, photos, `dgc/`, `scratch/`, `graphify-out/`; untracked the stray `stt_experiments` recording. `gemini_tools` scripts load `.env` relative to the repo instead of an absolute home path.

## [2026-10-07] - Embed fonts into PowerPoint decks
- feat: `document_converters/pptx_embed_fonts.py` — `IN.pptx OUT.pptx FONT.ttf...` embeds TrueType fonts so a deck renders on machines without them. Matches each font to a typeface the deck actually uses (legacy family, typographic family or full name, case-insensitive; a full-name match like "Lato Light Italic" goes in the regular slot), picks the style slot from nameID 2 (some static instances have wrong fsSelection bits), keeps existing embedded entries and fills only empty slots. Writes uncompressed EOT v2.2 `.fntdata` (layout checked against Google Slides exports). Refuses CFF `.otf` and variable fonts (instantiate a static TTF first). `--selftest`.

## [2026-10-06] - Telegram QR login survives a pending 2FA session
- fix: `chat_tools/qr_login.py` — when a previous scan left the session waiting on the 2FA password, `qr_login()` raised `SessionPasswordNeededError` outside the try and crashed; it now prompts for the password instead.

## [2026-09-17] - Word comments and tracked deletions on exact text
- feat: `document_converters/docx_comment.py` — anchor a Word comment on exact text (paragraphs + table cells), splitting runs so the range covers only the phrase. `IN OUT --find TEXT --comment MSG` or `--batch json`; never overwrites IN. `--selftest`.
- feat: `document_converters/docx_track_delete.py` — delete text as Word tracked changes (`w:del`). `track_delete(src, dst, find_spans, author)` takes a callback over each paragraph's current text; existing insertions/deletions, hyperlinks, fields and tab/break runs are treated as barriers (spans touching them are skipped, not half-applied). `views()` returns accepted/rejected text for verification. `--selftest`.

## [2026-09-17] - Find documents among thousands of photos
- feat: `image_tools/vision_scan.swift` — on-device Apple Vision over folders of photos: default mode prints scene labels (e.g. `document`, `printed_page`, `passport`) to shortlist paperwork; `--text-fast` reads English/French text. `--text` (accurate) is unreliable on macOS 27.0 (e5rtError 13 partway through runs) — documented in the file. Build with `swiftc -O` outside `/tmp`.
- feat: `image_tools/contact_sheet.py` — tiles many images (HEIC via `sips`) into numbered grids + `index.tsv`, for reviewing hundreds of candidates quickly.
- feat: `ocr_tools/ocr_images.py` — Cloud Vision OCR over a list of photos into a JSONL cache (shrinks to JPEG first; skips cached paths so reruns never pay twice; failures uncached). Reuses `pdf_ocr.ocr_image` + bifrost client. `--selftest`.

## [2026-09-17] - Move photos by the date they were taken
- feat: `image_tools/move_by_capture_date.py` — `SRC... DEST --from YYYY-MM [--to YYYY-MM] [--by-month] [--apply]`. SRC is a folder (files are moved) or zip files (only matching files are extracted, via a `.part` rename so an interrupted run leaves no truncated file; reruns skip same-size files). Picks photos/videos whose embedded date (EXIF for JPG/HEIC/PNG, QuickTime `creationdate`/`mvhd` for MOV/MP4) falls in the range. Dry run by default; skips files modified in the last 2 minutes so it can run beside an unzip in progress; never overwrites. Files with no embedded date (saved/received images, screenshots) stay put. `--selftest` checks the parsers offline.

## [2026-09-14] - Vision paragraphs with bounding boxes
- feat: `ocr_tools/pdf_ocr.py` — `ocr_image_paragraphs(png_bytes, client)` returns Vision paragraphs as `{"text", "box"}` in the image's pixel space, with detected word and line breaks kept in the text; `paragraphs_from_annotation` does the flattening and is testable offline. For cropping a known piece of text (a headword, an item number) out of a scanned page.

## [2026-09-14] - Read selected PDF pages (OCR or copy-only Gemini)
- feat: `ocr_tools/pdf_page_reader.py` — `pick_pages` (title pages + middle + last), `ocr_pdf_pages` (Cloud Vision over those pages, reusing `pdf_ocr`), `transcribe_pdf_pages` (Gemini copies printed text into caller's JSON schema with `COPY_ONLY_RULES`). For identifying scanned documents with meaningless filenames. Warning recorded in the module: on degraded Khmer scans Gemini flash and pro both invented title subjects at high confidence, so prefer the Vision path and verify Gemini output.

## [2026-09-14] - Vertex region override
- feat: `gemini_tools/transcribe_audio.py` — `get_vertex_client(location=None)` takes an optional region. Existing calls are unchanged (Bifrost's `VERTEX_AI_LOCATION`, else `asia-southeast1`). Added because `gemini-2.5-pro` returns 404 in `asia-southeast1` and is served in `us-central1` / `global`.

## [2026-08-14] - PDF to PPTX conversion
- feat: `document_converters/pdf_to_pptx.py` — Generic utility script to convert PDFs into high-resolution PPTX files using PyMuPDF and python-pptx.

## [2026-08-11] - PPTX translation
- feat: `document_converters/pptx_translate.py` — layout-preserving .pptx translation for any language pair. Rewrites text in place (images, fonts, placement untouched), translates each text box as a whole so a sentence broken across lines is not translated in halves, and takes house terminology from an external `--glossary` json (`render` / `keep_english` / `notes`) so no project vocabulary lives in the tool. `--dry-run` prints what would be sent; `--selftest` checks the parsing and write-back logic offline.

## [2026-07-27] - Audio Transcription, Governance & PPTX Meeting Minutes Exporter
- feat: `gemini_tools/transcribe_audio.py` — Vertex AI Gemini 2.5 Flash verbatim audio transcription pipeline with automatic FFmpeg 16kHz mono chunking.
- feat: `gemini_tools/format_and_export_docx.py` — Idea-by-idea & Taskforce Governance Manual generator with Kantumruy Pro typography, natural Khmer spacing, and code-switched English term preservation.
- feat: `gemini_tools/generate_meeting_minutes.py` — PPTX slide flow extractor & Meeting Minutes generator matching presentation agenda in Kantumruy Pro DOCX.



## [2026-07-24] - Shared utility hub
- feat: `ocr_tools/pdf_ocr.py` — `render_pdf_page` / `ocr_image` / `ocr_pdf_page` glue (Vision client sourced from bifrost).
- feat: `json_tools/gemini_json.py` — `strip_json_fences` / `parse_gemini_json` for Gemini responses.
- docs: `AGENTS.md` establishing this repo as the cross-project utility hub (reuse + upgrade here; keep project-specific code out).

## [2026-07-24] - Workspace Cleanup
- chore: Reorganized loose scripts, assets, and data files into proper subdirectories to clean up project roots.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2026-07-14]
### Added
- Khmer Speech-to-Text (STT) pipeline using Demucs for vocal isolation and Gemini Flash for high-accuracy transcription of singing lyrics.
- `random_stt_agents.md` logbook documenting the STT model experiments and pipeline evolution.

### Changed
- Consolidated `stt_experiments` into a single `transcribe_khmer_vocals.py` script and removed obsolete STT test scripts and model files.
- Organized `scratch/` directory by deleting log/output files and moving PPTX tools and timer scripts into dedicated subfolders (`pptx_tools`, `timer_tools`, `poster_gen`).

## [Unreleased]

### Changed
- Fixed path resolution in `spotify/spotify_api_fetcher.py` to correctly import local utils.
- Refactored `mac-cleaner` frontend CSS and React components for improved UI states and layout.
- Updated `ok.py` spot-the-difference script.
- Cleaned up obsolete scripts (`convert_pdf_to_pptx.py`, `fix_pptx_backgrounds.py`) and test files (`IMG_4633.HEIC`).

### Added
- **Countdown Timer Generation**:
  - Created `scratch/generate_timer.py` script to generate a customizable Full HD (1920x1080) timer video with a white background, huge centered black text, and warning/alarm beeps.
  - Added support for a 5-minute countdown that sounds a 3-beep warning (spaced by 100ms) when the timer hits `4:00` remaining.
  - Generated the final `downloads/5 Minute Timer.mp4` video.
- **PowerPoint Presentation Review**:
  - Created batch scripts `scratch/inspect_pptx.py`, `scratch/review_text_slides.py`, and `scratch/review_image_slides.py` to analyze 123 slides of `EGD_Slide Presentaton_DA5.pptx` for typos, grammar, and translation issues.
  - Created `scratch/check_duplicates_and_empty.py` and `scratch/check_slide_72.py` to map duplicate slides, identifying a 12-slide redundant block (slides 66-77).
  - Created `scratch/convert_to_pdf.py` to convert the 285MB presentation into a 48MB PDF natively on macOS via AppleScript.
  - Created `scratch/synthesize_results.py` to merge textual and visual findings into a comprehensive synthesis summary.

### Changed
- **Bifrost Integration**: Consolidated local `utils/bifrost_config.py` into a redirection proxy to consume the central client SDK, and refactored it with a hybrid local-prod resolver that queries the live API directly when local workspace paths are absent.

### Added
- Added `image_tools/enterprisedigital_qr.png` and standard code assets.
- Added `developer_reimplementation_prompt.md` document draft.
- Added `patch.py` utility patch script.
- Added `bkd.txt` and `IMG_4633.HEIC` diagnostic testing inputs.
- Created `mac-cleaner` folder containing a CleanMyMac-inspired storage cleaner application.
  - Built a Python FastAPI backend for recursively scanning specific directories (`~/Library/Caches`, `.npm`, `~/.Trash`).
  - Built a React + Vite frontend with glassmorphism UI, a central storage visualizer gauge, and action controls to safely delete files.
  - Implemented a Space Lens feature to inspect the sizes of arbitrary folders on the local system.
  - Implemented an MD5-based duplicate file scanner that detects and groups identical files over 1MB, automatically keeping one copy safe.
  - Added warning labels and safe defaults for developer caches (`pip`, `npm`, `ms-playwright`).

### Added
- Created `image_tools/generate_qr.py` as a standalone command line tool to generate QR codes with custom styling options. Added `qrcode` to dependencies.
- **Synchronous Config Pull**: Embedded Bifrost SDK directly into `bifrost_config.py` to synchronously pull and inject API keys straight into local memory at boot, removing the need for `bifrost_local.py` or webhook servers.

### Added
- Created `social_tools/run_scheduler.py` to run the TikTok Streak Keeper daily at 12:02 AM inside persistent containers.
- Created `Dockerfile` in the workspace root for containerized deployment (e.g. on Koyeb).
- Created `social_tools/tiktok_streak_keeper.py`, a browser automation utility using Playwright to automatically detect and message all friends with active streaks (or specified friends) to maintain them.
- Created `document_converters/pdf_merger.py`, a command line utility to merge multiple PDF files.
- Generalized `document_converters/pdf_extract_page.py` to allow extracting specific pages or page ranges using the `-p` flag.
- Added `pypdf` and `playwright` dependencies to virtual environment and registered them in `requirements.txt`.

### Changed
- **TikTok Streak Keeper Anti-Detection**: Upgraded browser automation to utilize `playwright-stealth` (if available), random desktop User Agents, and randomized viewports.
- **Humanized Timing**: Replaced rigid waits with randomized human-like delays for typing, clicking, and scrolling, and implemented a Gaussian delay distribution (15-120 seconds, mean 45s) between messaging different friends.
- **Streak Timing & Jitter**: Updated the daily scheduler to trigger at 11:00 PM with 0-20 minutes random daily jitter to ensure all messages complete sending well before the midnight reset.
- **Optional Residential Proxy**: Added support for residential proxy configuration via the `TIKTOK_PROXY` environment variable.
- Reorganized directory structure to use standardized `snake_case` folder and file naming.
- Consolidated image converters and compressors from `imagConverter/` and `imgCompressor/` into `image_tools/`.
- Moved standalone scripts from root directory to category folders with descriptive `snake_case` names:
  - `aja.py` -> `chat_tools/rewrite_html_paths.py`
  - `btscan.py` -> `system_tools/bluetooth_scanner.py`
  - `ok.py` -> `spot_the_difference/simple_diff.py`
  - `tmdb.py` -> `media_enricher/tmdb.py`
- Relocated puzzle image files to a nested `spot_the_difference/puzzles/` directory.
- Updated path resolution in scripts to resolve files relative to the script location instead of the current working directory:
  - `spot_the_difference/simple_diff.py`
  - `ocr_tools/ocr_only.py`
  - `ocr_tools/process_batch.py`
  - `ocr_tools/gemini.py`
  - `ocr_tools/main.py`
- Fixed macOS clipboard compatibility in `ocr_tools/main.py` using `pbcopy`.
- Updated `.gitignore` to match the newly organized directory structure.

## [Unreleased]
### Added
- Migrated `ocr_tools/main.py` from Google AI Studio to Google Cloud Vertex AI SDK.
