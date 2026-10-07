"""Turn icon-font ligature words ("videocam", "person") into real icon characters in a .pptx.

    python3 pptx_icon_ligatures.py IN.pptx OUT.pptx ICONFONT.ttf ["Material Icons"]
    python3 pptx_icon_ligatures.py --selftest

Google Slides draws Material Icons by typing the icon's name and letting the font's
ligatures swap it for the glyph. PowerPoint does not apply those ligatures, so the
name shows as plain text. This rewrites each run set in the icon font whose text is a
known ligature name to the glyph's codepoint (read from the font's own GSUB table).
"""
import sys

from fontTools.ttLib import TTFont

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def ligature_map(font_path):
    """{'videocam': 0xe04b, ...} from the font's ligature substitutions."""
    font = TTFont(font_path)
    rev = {g: c for c, g in font.getBestCmap().items()}
    out = {}
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for first, ligs in getattr(st, "ligatures", {}).items():
                for lig in ligs:
                    glyphs = [first] + lig.Component
                    if lig.LigGlyph in rev and all(g in rev for g in glyphs):
                        out["".join(chr(rev[g]) for g in glyphs)] = rev[lig.LigGlyph]
    return out


def fix_runs(root, typeface, ligs):
    """Rewrite matching runs under an lxml element; returns list of (name, codepoint)."""
    done = []
    for r in root.iter(A + "r"):
        rpr, t = r.find(A + "rPr"), r.find(A + "t")
        lat = rpr.find(A + "latin") if rpr is not None else None
        if t is None or lat is None or lat.get("typeface") != typeface:
            continue
        name = (t.text or "").strip()
        if name in ligs:
            t.text = chr(ligs[name])
            done.append((name, ligs[name]))
    return done


def fix_pptx(src, dst, font_path, typeface="Material Icons"):
    from pptx import Presentation

    ligs = ligature_map(font_path)
    prs = Presentation(src)
    report = []
    for i, slide in enumerate(prs.slides, 1):
        report += [(i, n, cp) for n, cp in fix_runs(slide._element, typeface, ligs)]
    for part in {l.part for m in prs.slide_masters for l in m.slide_layouts} | {m.part for m in prs.slide_masters}:
        report += [("layout/master", n, cp) for n, cp in fix_runs(part._element, typeface, ligs)]
    prs.save(dst)
    return report


def _selftest():
    from lxml import etree
    xml = (f'<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="{A[1:-1]}">'
           '<a:r><a:rPr><a:latin typeface="Material Icons"/></a:rPr><a:t>videocam</a:t></a:r>'
           '<a:r><a:rPr><a:latin typeface="Arial"/></a:rPr><a:t>videocam</a:t></a:r>'
           '<a:r><a:rPr><a:latin typeface="Material Icons"/></a:rPr><a:t>not_an_icon</a:t></a:r></p:sp>')
    root = etree.fromstring(xml)
    done = fix_runs(root, "Material Icons", {"videocam": 0xE04B})
    texts = [t.text for t in root.iter(A + "t")]
    assert done == [("videocam", 0xE04B)] and texts == ["", "videocam", "not_an_icon"], texts
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        _selftest()
    elif len(sys.argv) in (4, 5):
        for row in fix_pptx(*sys.argv[1:]):
            print(f"slide {row[0]}: {row[1]} -> U+{row[2]:04X}")
    else:
        sys.exit(__doc__)
