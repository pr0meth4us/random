"""Read selected pages of a PDF: OCR them, or have Gemini copy printed text.

Built for identifying scanned documents whose filenames and metadata say
nothing — read the pages that carry identity (title pages, the last page where
the date and signature sit, one from the middle) instead of the whole file.

Two backends, and they fail differently:

- `ocr_pdf_pages` (Cloud Vision) is a real OCR engine. It misreads characters;
  it does not invent a plausible title. Prefer it for identification.
- `transcribe_pdf_pages` (Gemini) returns structured JSON, but a generative
  model will write plausible text it did not see — on degraded Khmer scans both
  gemini-2.5-flash and -pro replaced the subject of document titles while
  reporting high confidence, even under COPY_ONLY_RULES. Verify its output
  against the page before relying on it.

    import sys
    sys.path.insert(0, "/Users/nicksng/code/random")
    from ocr_tools.pdf_page_reader import pick_pages, ocr_pdf_pages, transcribe_pdf_pages
"""
import time

COPY_ONLY_RULES = """Rules:
- COPY text. Do not identify, name, date or summarise the document.
- Copy characters exactly as printed. Do not fix spelling, expand abbreviations,
  translate, or finish partial words.
- Never write text that is not visible in these images. Do not use background
  knowledge about institutions, laws or publications to fill a gap.
- If part of a line is unreadable, copy the readable part and write … for the rest.
- If there is nothing to copy for a field, use [] or null. An empty answer is
  correct. A guessed one is wrong.
Output ONLY the JSON object. No markdown fences, no commentary."""


def pick_pages(page_count, head=3, middle=True, tail=1):
    """0-based page indexes that usually carry a document's identity."""
    if page_count <= 0:
        return []
    wanted = set(range(min(head, page_count)))
    if middle:
        wanted.add(page_count // 2)
    wanted.update(range(max(0, page_count - tail), page_count))
    return sorted(wanted)


def ocr_pdf_pages(pdf_path, pages=None, client=None, dpi=200):
    """Cloud Vision OCR of selected pages -> {page_index: text}.

    `pages` defaults to pick_pages(). Raises RuntimeError on a Vision API error
    (a disabled API arrives here as PermissionDenied from the client).
    """
    import fitz

    from ocr_tools.pdf_ocr import _default_vision_client, ocr_image, render_pdf_page

    client = client or _default_vision_client()
    doc = fitz.open(pdf_path)
    try:
        indexes = pick_pages(doc.page_count) if pages is None else pages
        return {i: ocr_image(render_pdf_page(doc, i, dpi), client) for i in indexes}
    finally:
        doc.close()


def build_parts(doc, pages, first_dpi=150, other_dpi=110):
    """Gemini content parts: a "Page N of M:" label before each page image."""
    from google import genai

    parts = []
    for i in pages:
        parts.append(f"Page {i + 1} of {doc.page_count}:")
        png = doc[i].get_pixmap(dpi=first_dpi if i == pages[0] else other_dpi).tobytes("png")
        parts.append(genai.types.Part.from_bytes(data=png, mime_type="image/png"))
    return parts


def transcribe_pdf_pages(pdf_path, schema_prompt, client, model="gemini-2.5-pro",
                         pages=None, retries=3):
    """Ask Gemini to copy text from selected pages into `schema_prompt`'s JSON.

    `schema_prompt` describes the JSON wanted; COPY_ONLY_RULES is appended.
    Returns (parsed_json, page_count). Raises the last error after `retries`.
    Hold a reference to `client` for the whole run: a temporary genai client is
    closed when garbage-collected, and later calls fail with "client has been
    closed".
    """
    import fitz

    from json_tools.gemini_json import parse_gemini_json

    doc = fitz.open(pdf_path)
    try:
        count = doc.page_count
        indexes = pick_pages(count) if pages is None else pages
        parts = build_parts(doc, indexes) if indexes else []
    finally:
        doc.close()
    if not parts:
        raise ValueError(f"{pdf_path}: no pages to read")

    prompt = schema_prompt.rstrip() + "\n\n" + COPY_ONLY_RULES
    for attempt in range(retries):
        try:
            res = client.models.generate_content(model=model, contents=[prompt, *parts])
            return parse_gemini_json(res.text), count
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(4 * (attempt + 1))


if __name__ == "__main__":
    # Offline self-check: page selection only (no fitz/google calls).
    assert pick_pages(0) == []
    assert pick_pages(1) == [0]
    assert pick_pages(2) == [0, 1]
    assert pick_pages(5) == [0, 1, 2, 4]
    assert pick_pages(123) == [0, 1, 2, 61, 122]
    assert pick_pages(10, head=1, middle=False, tail=2) == [0, 8, 9]
    assert "Never write text that is not visible" in COPY_ONLY_RULES
    print("pdf_page_reader self-check passed")
