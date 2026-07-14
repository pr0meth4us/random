# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [2026-07-14]
### Added
- Khmer Speech-to-Text (STT) pipeline using Demucs for vocal isolation and Gemini Flash for high-accuracy transcription of singing lyrics.
- `random_stt_agents.md` logbook documenting the STT model experiments and pipeline evolution.

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
