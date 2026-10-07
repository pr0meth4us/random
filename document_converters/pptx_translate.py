#!/usr/bin/env python3
"""Translate a .pptx in place-preserving fashion: layout, images and fonts stay,
only the text is replaced.

Generic — any language pair, any deck. Project-specific terminology is supplied
from the outside via --glossary, so no house vocabulary lives in this file.

    python pptx_translate.py in.pptx out.pptx --to English
    python pptx_translate.py in.pptx out.pptx --to English --from Khmer \
        --glossary house_lexicon.json --model gemini-2.5-pro

Glossary json (all keys optional):
    {"render": {"smart technology": "..."},     # source-lang -> target-lang
     "keep_english": ["EGD", "MSME"],           # never translate / never alter
     "notes": "free text appended to the prompt"}

Each text box is translated as a whole (its paragraphs rejoined with \n) so a
sentence broken across two lines is not translated in halves.

Write-back is per paragraph: the translation lands in the paragraph's first run
(inheriting its font) and the remaining runs are emptied. Intra-paragraph run
styling (a bold word mid-sentence) is therefore lost; paragraph-level styling,
placement and every non-text part of the deck are untouched.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from pptx import Presentation

SDK = "/Users/nicksng/code/bifrost/sdk/python"

# Pure-ASCII frames (slide numbers, URLs, "1.", already-Latin titles) are left
# alone — nothing to translate, and sending them only invites invention. The test
# is script, not letters: a frame of Khmer numerals (១២៣) IS translatable work,
# since the target language writes its digits differently.
NEEDS_WORK = re.compile(r"[^\x00-\x7f]")
# Batch size is about prompt hygiene, not token limits: long JSON arrays are
# where models start dropping or merging entries.
BATCH = 20
# A generate_content call with no deadline can hang forever on a stalled
# connection — observed: one batch sat blocked with zero CPU until killed by
# hand. Every call gets a deadline and a retry instead.
TIMEOUT_MS = 180_000


def iter_text_frames(shapes):
    """Yield every text frame in a shape tree, descending into groups/tables."""
    for shape in shapes:
        if shape.shape_type == 6:  # GROUP
            yield from iter_text_frames(shape.shapes)
            continue
        if getattr(shape, "has_table", False) and shape.has_table:
            for row in shape.table.rows:
                for cell in row.cells:
                    yield cell.text_frame
            continue
        if shape.has_text_frame:
            yield shape.text_frame


def collect(prs):
    """Return [(paragraphs, text)] per text frame, one unit of translation each.

    A frame is translated whole, not paragraph by paragraph: slide text boxes
    routinely break one sentence across paragraphs ("...digital solutions" /
    "before in business operations"), and a half-sentence handed to the model
    alone comes back as nonsense. Paragraphs are rejoined with \\n and split back
    out after translation.
    """
    items = []
    for slide in prs.slides:
        for frame in iter_text_frames(slide.shapes):
            paras = [p for p in frame.paragraphs if p.runs]
            text = "\n".join("".join(r.text for r in p.runs) for p in paras)
            if text.strip() and NEEDS_WORK.search(text):
                items.append((paras, text))
    return items


def build_prompt(texts, src, dst, glossary):
    lines = [
        f"Translate each item from {src or 'its source language'} into {dst}.",
        "",
        "Rules:",
        "- These are presentation slides: keep translations tight and title-like,"
        " not expanded prose. Never add explanation.",
        "- Each item is one text box. A newline (\\n) is a line break inside it:"
        " return EXACTLY as many lines as the item has, breaking the translation"
        " at the same points even when that splits a sentence.",
        "- Preserve vertical-tabs (\\x0b) exactly where they are; they are soft"
        " line breaks.",
        "- Preserve leading/trailing spaces.",
        "- Translate quoted terms too, keeping the quotation marks.",
        "- Convert numerals to the target language's usual digits.",
        "- If an item is already in the target language, return it unchanged.",
    ]
    if glossary.get("keep_english"):
        lines.append("- Leave these exactly as-is, never translate or expand: "
                     + ", ".join(glossary["keep_english"]))
    if glossary.get("render"):
        pairs = "; ".join(f'"{k}" -> "{v}"' for k, v in glossary["render"].items()
                          if not str(v).startswith("["))
        if pairs:
            lines.append("- Required terminology (use these exact renderings, in "
                         f"either direction): {pairs}")
    if glossary.get("notes"):
        lines.append("- " + glossary["notes"])
    lines += [
        "",
        f"Return ONLY a JSON array of exactly {len(texts)} strings, in the same"
        " order. No markdown fence, no commentary.",
        "",
        json.dumps(texts, ensure_ascii=False, indent=1),
    ]
    return "\n".join(lines)


def parse_array(raw, n):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw.split("\n", 1)[1] if raw.lower().startswith("json") else raw
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < 0:
        raise ValueError(f"no JSON array in model output: {raw[:200]!r}")
    out = json.loads(raw[start:end + 1])
    if len(out) != n:
        raise ValueError(f"model returned {len(out)} items, expected {n}")
    return out


def translate_texts(texts, src, dst, glossary, model):
    sys.path.insert(0, SDK)
    from bifrost_ai import get_genai_client
    client = get_genai_client()

    out = []
    for i in range(0, len(texts), BATCH):
        chunk = texts[i:i + BATCH]
        prompt = build_prompt(chunk, src, dst, glossary)
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model, contents=prompt,
                    config={"http_options": {"timeout": TIMEOUT_MS}})
                out.extend(parse_array(resp.text, len(chunk)))
                break
            except Exception as exc:  # transport timeouts included
                if attempt == 2:
                    raise
                print(f"  retry {attempt + 1}: {exc}", file=sys.stderr)
        print(f"  translated {min(i + BATCH, len(texts))}/{len(texts)}",
              file=sys.stderr)
    return out


def write_back(paras, text):
    """Split `text` back over `paras`, one line each.

    The model occasionally returns a different number of lines than it was
    given; rather than fail the whole deck, extra lines are glued onto the last
    paragraph and missing ones leave a paragraph empty. Layout survives either
    way, and the deck still needs a human read-through.
    """
    lines = text.split("\n")
    if len(lines) > len(paras):
        lines = lines[:len(paras) - 1] + ["\n".join(lines[len(paras) - 1:])]
    lines += [""] * (len(paras) - len(lines))
    for para, line in zip(paras, lines):
        para.runs[0].text = line
        for run in para.runs[1:]:
            run.text = ""


def translate_pptx(src_path, out_path, *, src_lang, dst_lang, glossary, model,
                   dry_run=False):
    prs = Presentation(src_path)
    items = collect(prs)
    texts = [t for _, t in items]
    if dry_run:
        print(json.dumps(texts, ensure_ascii=False, indent=1))
        return texts
    translated = translate_texts(texts, src_lang, dst_lang, glossary, model)
    for (paras, _), new in zip(items, translated):
        write_back(paras, new)
    prs.save(out_path)
    return translated


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--to", dest="dst", required=True, help="target language")
    ap.add_argument("--from", dest="src", default=None, help="source language")
    ap.add_argument("--glossary", help="json file: render / keep_english / notes")
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the extracted paragraphs and exit")
    args = ap.parse_args()

    glossary = json.loads(Path(args.glossary).read_text(encoding="utf-8")) \
        if args.glossary else {}
    translate_pptx(args.input, args.output, src_lang=args.src, dst_lang=args.dst,
                   glossary=glossary, model=args.model, dry_run=args.dry_run)
    if not args.dry_run:
        print(args.output)


def _selftest():
    """assert-based check of the pure logic (no model, no file needed)."""
    assert parse_array('```json\n["a","b"]\n```', 2) == ["a", "b"]
    assert parse_array('here you go: ["a"] ok', 1) == ["a"]
    try:
        parse_array('["a"]', 2)
    except ValueError:
        pass
    else:
        raise AssertionError("length mismatch not caught")
    assert NEEDS_WORK.search("7") is None and NEEDS_WORK.search("EGD") is None
    assert NEEDS_WORK.search("៧") and NEEDS_WORK.search("ជំនួយ")
    p = build_prompt(["x"], "Khmer", "English", {"keep_english": ["EGD"]})
    assert "EGD" in p and "exactly 1" in p

    class _Run:
        def __init__(self, t=""):
            self.text = t

    class _Para:
        def __init__(self):
            self.runs = [_Run(), _Run("stale")]

    ps = [_Para(), _Para()]
    write_back(ps, "one\ntwo")
    assert [p.runs[0].text for p in ps] == ["one", "two"]
    assert all(p.runs[1].text == "" for p in ps)
    ps = [_Para(), _Para()]
    write_back(ps, "one\ntwo\nthree")          # too many lines -> glued
    assert [p.runs[0].text for p in ps] == ["one", "two\nthree"]
    ps = [_Para(), _Para()]
    write_back(ps, "only")                     # too few -> padded
    assert [p.runs[0].text for p in ps] == ["only", ""]
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
