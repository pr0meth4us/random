"""Anchor Word comments on exact text in a .docx (paragraphs and table cells).

    python docx_comment.py IN.docx OUT.docx --find TEXT --comment MSG [--author NAME] [--initials XX] [--nth N]
    python docx_comment.py IN.docx OUT.docx --batch comments.json   # [{"find", "comment", "nth"?}, ...]
    python docx_comment.py --selftest

The comment covers exactly TEXT: runs are split at the match boundaries (formatting
copied), so a phrase spread over several runs is still one clean range. Never
writes over IN unless OUT is the same path and --in-place is given.
"""
import argparse, copy, json, sys
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run


def _split(run: Run, offset: int) -> Run:
    """Split run at text offset; return the right-hand run (inserted after run)."""
    right = copy.deepcopy(run._r)
    run._r.addnext(right)
    text = run.text
    run.text, Run(right, run._parent).text = text[:offset], text[offset:]
    return Run(right, run._parent)


def _paragraphs(doc):
    for p in doc.element.body.iter(qn("w:p")):
        yield Paragraph(p, doc._body)


def find_runs(doc, text: str, nth: int = 1):
    """Return (first_run, last_run) covering the nth occurrence of text, splitting runs as needed."""
    seen = 0
    for para in _paragraphs(doc):
        runs = para.runs
        joined = "".join(r.text for r in runs)
        start = -1
        while True:
            start = joined.find(text, start + 1)
            if start < 0:
                break
            seen += 1
            if seen == nth:
                return _cover(runs, start, start + len(text))
    raise LookupError(f"occurrence {nth} of {text!r} not found (found {seen}; text inside hyperlinks/text boxes is not searched)")


def _cover(runs, start, end):
    pos, first, last = 0, None, None
    for r in runs:
        r_start, r_end = pos, pos + len(r.text)
        pos = r_end
        if first is None and r_start <= start < r_end:
            if start > r_start:
                r = _split(r, start - r_start)
                r_start = start
            first = r
        if first is not None and r_start < end <= r_end:
            if end < r_end:
                _split(r, end - r_start)
            last = r
            break
    return first, last


def add_comments(src, dst, items, author="", initials=""):
    doc = Document(src)
    for it in items:
        first, last = find_runs(doc, it["find"], it.get("nth", 1))
        doc.add_comment([first, last], text=it["comment"], author=author, initials=initials)
    doc.save(dst)


def _selftest():
    import os, tempfile
    d = tempfile.mkdtemp()
    src, dst = os.path.join(d, "a.docx"), os.path.join(d, "b.docx")
    doc = Document()
    p = doc.add_paragraph()
    for chunk in ("Keep this. ស្របតាម", "គោលនយោបាយ ", "ឌីជីថល។ tail"):
        p.add_run(chunk).bold = chunk.startswith("គោល")
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "cell target here"
    doc.save(src)
    add_comments(src, dst, [{"find": "ស្របតាមគោលនយោបាយ ឌីជីថល", "comment": "why"},
                            {"find": "target", "comment": "in table"}], author="T")
    out = Document(dst)
    assert [c.text for c in out.comments] == ["why", "in table"], [c.text for c in out.comments]
    body = out.element.body
    ranges = []
    for start in body.iter(qn("w:commentRangeStart")):
        cid, text, on = start.get(qn("w:id")), [], False
        for el in body.iter():
            if el is start:
                on = True
            elif el.tag == qn("w:commentRangeEnd") and el.get(qn("w:id")) == cid:
                break
            elif on and el.tag == qn("w:t"):
                text.append(el.text or "")
        ranges.append("".join(text))
    assert ranges == ["ស្របតាមគោលនយោបាយ ឌីជីថល", "target"], ranges
    assert out.paragraphs[0].text == "Keep this. ស្របតាមគោលនយោបាយ ឌីជីថល។ tail"
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?"); ap.add_argument("dst", nargs="?")
    ap.add_argument("--find"); ap.add_argument("--comment"); ap.add_argument("--nth", type=int, default=1)
    ap.add_argument("--batch"); ap.add_argument("--author", default=""); ap.add_argument("--initials", default="")
    ap.add_argument("--in-place", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not (a.src and a.dst):
        ap.error("IN.docx and OUT.docx are required")
    if a.src == a.dst and not a.in_place:
        ap.error("OUT is the same as IN; pass --in-place to overwrite")
    items = json.load(open(a.batch, encoding="utf-8")) if a.batch else [{"find": a.find, "comment": a.comment, "nth": a.nth}]
    if not all(i.get("find") and i.get("comment") for i in items):
        ap.error("each comment needs find + comment")
    add_comments(a.src, a.dst, items, a.author, a.initials)
    print(f"{len(items)} comment(s) -> {a.dst}")


if __name__ == "__main__":
    sys.exit(main())
