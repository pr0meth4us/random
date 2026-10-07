# random — the shared utility hub for ~/code

This repo (github: `pr0meth4us/random`) is the **cross-project utility library**
for everything under `~/code`. Generic, reusable helpers live here so there is
ONE battle-tested implementation that every project shares and keeps improving —
instead of each project re-hand-rolling (and re-breaking) the same OCR / Gemini /
json / download / conversion logic in its own `scratch/`.

## Rules for agents — every project, every tool

1. **Reuse before you write.** Need a *generic* utility — OCR a PDF, call
   Gemini/Vertex, prettify json, download media, convert a doc, resize an image?
   Look here first: `ocr_tools/`, `gemini_tools/`, `json_tools/`,
   `document_converters/`, `downloaders/`, `image_tools/`, `system_tools/`,
   `utils/`. Import it; do not reimplement it in your project.

2. **Upgrade here, not around it.** If the existing helper doesn't fit your case,
   improve it *in this repo* — generalize it, add a parameter, fix the edge case —
   so the next project inherits the fix. Keep changes backward-compatible and note
   them in `CHANGELOG.md`. A worse copy in your own project is the failure mode
   this repo exists to prevent.

3. **Keep it generic.** Only project-agnostic utilities belong here. Anything
   specialized to one project — its API client, its domain pipeline, its data —
   stays in that project. Don't pollute `random` with project-specific logic.

4. **Cross-repo import pattern** (Python — this repo is not pip-installed):

       import sys
       sys.path.insert(0, "/Users/nicksng/code/random")
       from ocr_tools.google_vision import extract_text
       from utils.bifrost_config import get_config

## What's here

`ocr_tools` (Cloud Vision OCR + dictionary indexing) · `gemini_tools` (Gemini
chat / model listing) · `json_tools` · `document_converters` (pdf/excel/txt) ·
`downloaders` (yt→m4a) · `image_tools` · `system_tools` (secrets/env, bluetooth) ·
`utils` (`bifrost_config` credential resolver). Run `pip install -r requirements.txt`.
