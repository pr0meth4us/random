"""Render PDF pages and OCR them with Cloud Vision.

The Vision client *and its credentials* come from bifrost (`bifrost_ai`). This
module is only the PyMuPDF + OCR glue on top: turn a PDF page into PNG bytes and
run document text detection. Pass your own `client` to reuse one across many
pages; omit it and one is fetched from bifrost lazily.

    from ocr_tools.pdf_ocr import render_pdf_page, ocr_image, ocr_pdf_page
"""

_BIFROST_SDK = "/Users/nicksng/code/bifrost/sdk/python"


def render_pdf_page(doc, page_num, dpi=150):
    """One page of an open fitz (PyMuPDF) document -> PNG bytes."""
    return doc.load_page(page_num).get_pixmap(dpi=dpi).tobytes("png")


def _default_vision_client():
    import sys

    if _BIFROST_SDK not in sys.path:
        sys.path.insert(0, _BIFROST_SDK)
    from bifrost_ai import get_vision_client

    return get_vision_client()


def ocr_image(png_bytes, client=None):
    """OCR PNG bytes -> text. Raises RuntimeError on a Vision API error."""
    from google.cloud import vision

    client = client or _default_vision_client()
    resp = client.document_text_detection(image=vision.Image(content=png_bytes))
    if resp.error.message:
        raise RuntimeError(f"Vision API error: {resp.error.message}")
    return resp.full_text_annotation.text


def ocr_pdf_page(pdf_path, page_num, dpi=150, client=None):
    """Convenience: open PDF, render one page, OCR it, return text."""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        png = render_pdf_page(doc, page_num, dpi)
    finally:
        doc.close()
    return ocr_image(png, client)


def paragraphs_from_annotation(annotation):
    """Flatten a Vision full_text_annotation into paragraphs with boxes.

    -> [{"text": str, "box": (x0, y0, x1, y1)}] in the pixel space of the image
    that was sent, in Vision's reading order. Word and line breaks detected by
    Vision become a space or a newline, so a paragraph's text can be matched
    line by line.
    """
    SPACE, SURE_SPACE, EOL_SURE_SPACE, HYPHEN, LINE_BREAK = 1, 2, 3, 4, 5
    out = []
    for page in annotation.pages:
        for block in page.blocks:
            for para in block.paragraphs:
                parts = []
                for word in para.words:
                    for sym in word.symbols:
                        parts.append(sym.text)
                        brk = getattr(getattr(sym.property, "detected_break", None), "type_", 0)
                        if brk in (SPACE, SURE_SPACE):
                            parts.append(" ")
                        elif brk in (EOL_SURE_SPACE, LINE_BREAK):
                            parts.append("\n")
                        elif brk == HYPHEN:
                            parts.append("-\n")
                xs = [v.x for v in para.bounding_box.vertices]
                ys = [v.y for v in para.bounding_box.vertices]
                out.append({"text": "".join(parts).strip(), "box": (min(xs), min(ys), max(xs), max(ys))})
    return out


def ocr_image_paragraphs(png_bytes, client=None):
    """OCR PNG bytes -> paragraphs with bounding boxes (see paragraphs_from_annotation).

    For cropping a known piece of text out of a page image. Raises RuntimeError
    on a Vision API error.
    """
    from google.cloud import vision

    client = client or _default_vision_client()
    resp = client.document_text_detection(image=vision.Image(content=png_bytes))
    if resp.error.message:
        raise RuntimeError(f"Vision API error: {resp.error.message}")
    return paragraphs_from_annotation(resp.full_text_annotation)


if __name__ == "__main__":
    # Self-check (no google/fitz deps): render_pdf_page passes dpi/page through.
    class _Pix:
        def tobytes(self, fmt):
            return f"PNG:{fmt}".encode()

    class _Page:
        def get_pixmap(self, dpi):
            assert dpi == 150
            return _Pix()

    class _Doc:
        def load_page(self, n):
            assert n == 3
            return _Page()

    assert render_pdf_page(_Doc(), 3) == b"PNG:png"

    # paragraphs_from_annotation: text with breaks, box from vertices
    from types import SimpleNamespace as NS

    def sym(t, brk=0):
        return NS(text=t, property=NS(detected_break=NS(type_=brk)))

    word1 = NS(symbols=[sym("៣"), sym("១"), sym("-", 1)])
    word2 = NS(symbols=[sym("ជ"), sym("ី", 5)])
    word3 = NS(symbols=[sym("H"), sym("."), sym(" ", 0), sym("x")])
    para = NS(words=[word1, word2, word3],
              bounding_box=NS(vertices=[NS(x=10, y=20), NS(x=90, y=20), NS(x=90, y=60), NS(x=10, y=60)]))
    ann = NS(pages=[NS(blocks=[NS(paragraphs=[para])])])
    got = paragraphs_from_annotation(ann)
    assert got == [{"text": "៣១- ជី\nH. x", "box": (10, 20, 90, 60)}], got
    print("pdf_ocr self-check passed")
