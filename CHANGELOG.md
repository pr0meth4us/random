# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- **Synchronous Config Pull**: Embedded Bifrost SDK directly into `bifrost_config.py` to synchronously pull and inject API keys straight into local memory at boot, removing the need for `bifrost_local.py` or webhook servers.

### Added
- Created `social_tools/run_scheduler.py` to run the TikTok Streak Keeper daily at 12:02 AM inside persistent containers.
- Created `Dockerfile` in the workspace root for containerized deployment (e.g. on Koyeb).
- Created `social_tools/tiktok_streak_keeper.py`, a browser automation utility using Playwright to automatically detect and message all friends with active streaks (or specified friends) to maintain them.
- Created `document_converters/pdf_merger.py`, a command line utility to merge multiple PDF files.
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
