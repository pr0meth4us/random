# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Created `document_converters/pdf_merger.py`, a command line utility to merge multiple PDF files.
- Added `pypdf` dependency to virtual environment and registered it in `requirements.txt`.

### Changed
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
