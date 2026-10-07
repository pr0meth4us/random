"""Embed TrueType fonts into a .pptx so it renders on machines that lack them.

    python3 pptx_embed_fonts.py IN.pptx OUT.pptx FONT.ttf [FONT.ttf ...]
    python3 pptx_embed_fonts.py --selftest

Each font is matched to a typeface the deck actually uses (case-insensitive,
by legacy family, typographic family, or full name) and stored in the slot its
style says (regular / bold / italic / boldItalic). Fonts the deck never uses
are skipped. Existing embedded entries are kept; empty slots are filled.

PowerPoint stores embedded fonts as EOT (`.fntdata`); this writes uncompressed
EOT v2.2 around the raw TrueType data. Only TrueType outlines (glyf) can be
embedded — CFF .otf and variable fonts are refused (instantiate a static TTF
first, e.g. `fontTools.varLib.instancer`).
"""
import io
import re
import struct
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RT_FONT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"
CT_FONT = "application/x-fontdata"
SLOTS = ("regular", "bold", "italic", "boldItalic")
EOT_ROOT_CHECKSUM_XOR = 0x50475342  # checksum of the (empty) root string, XOR'd per spec


def _name(font, name_id):
    rec = font["name"].getName(name_id, 3, 1, 0x409) or font["name"].getName(name_id, 1, 0, 0)
    return str(rec) if rec else ""


def _slot(font):
    # Legacy subfamily (nameID 2) first: some static instances ship with wrong fsSelection bits.
    by_name = {"regular": 0, "bold": 1, "italic": 2, "bold italic": 3}.get(_name(font, 2).lower())
    if by_name is not None:
        return SLOTS[by_name]
    sel = font["OS/2"].fsSelection
    bold, italic = bool(sel & 0x20), bool(sel & 0x01)
    return SLOTS[bold + 2 * italic]


def to_eot(ttf_bytes):
    """Wrap raw TrueType bytes in an uncompressed EOT v2.2 header."""
    font = TTFont(io.BytesIO(ttf_bytes))
    if "glyf" not in font:
        raise ValueError("not TrueType outlines (CFF/OTF cannot be embedded)")
    if "fvar" in font:
        raise ValueError("variable font: instantiate a static TTF first")
    os2 = font["OS/2"]
    panose = os2.panose
    body = bytearray()
    body += struct.pack("<I", 0x00020002) + struct.pack("<I", 0)  # version, flags (no compression/XOR)
    body += bytes([panose.bFamilyType, panose.bSerifStyle, panose.bWeight, panose.bProportion,
                   panose.bContrast, panose.bStrokeVariation, panose.bArmStyle, panose.bLetterForm,
                   panose.bMidline, panose.bXHeight])
    body += struct.pack("<BBIHH", 1, os2.fsSelection & 1, os2.usWeightClass, os2.fsType, 0x504C)
    body += struct.pack("<4I", os2.ulUnicodeRange1, os2.ulUnicodeRange2, os2.ulUnicodeRange3, os2.ulUnicodeRange4)
    body += struct.pack("<2I", getattr(os2, "ulCodePageRange1", 0), getattr(os2, "ulCodePageRange2", 0))
    body += struct.pack("<I4I", font["head"].checkSumAdjustment, 0, 0, 0, 0)
    for nid in (1, 2, 5, 4):  # family, style, version, full name
        s = _name(font, nid).encode("utf-16le")
        body += struct.pack("<HH", 0, len(s)) + s
    body += struct.pack("<HH", 0, 0)  # padding5, empty root string
    body += struct.pack("<IIHHII", EOT_ROOT_CHECKSUM_XOR, 0, 0, 0, 0, 0)
    total = 8 + len(body) + len(ttf_bytes)
    return struct.pack("<II", total, len(ttf_bytes)) + bytes(body) + ttf_bytes


def read_eot(blob):
    """Inverse check for to_eot: returns (names, font_bytes)."""
    total, size = struct.unpack_from("<II", blob, 0)
    assert total == len(blob)
    p = 16 + 10 + 1 + 1 + 4 + 2
    assert struct.unpack_from("<H", blob, p)[0] == 0x504C
    p += 2 + 16 + 8 + 4 + 16
    names = []
    for _ in range(4):
        n = struct.unpack_from("<H", blob, p + 2)[0]
        names.append(blob[p + 4:p + 4 + n].decode("utf-16le"))
        p += 4 + n
    return names, blob[len(blob) - size:]


def used_typefaces(prs):
    xml = []
    for part in prs.part.package.iter_parts():
        if str(part.partname).endswith(".xml") and re.search(r"/(slides|slideLayouts|slideMasters|theme)/", str(part.partname)):
            xml.append(part.blob.decode("utf8", "ignore"))
    return {t.lower(): t for t in re.findall(r'typeface="([^"+][^"]*)"', "".join(xml))}


def embed_fonts(src, dst, font_paths):
    from lxml import etree
    from pptx import Presentation
    from pptx.opc.package import Part
    from pptx.opc.packuri import PackURI

    prs = Presentation(src)
    used = used_typefaces(prs)
    pres = prs.part._element
    lst = pres.find(f"{{{P}}}embeddedFontLst")
    if lst is None:
        lst = etree.Element(f"{{{P}}}embeddedFontLst")
        pres.find(f"{{{P}}}notesSz").addnext(lst)
    pres.set("embedTrueTypeFonts", "1")
    pres.set("saveSubsetFonts", "0")
    taken = {str(p.partname) for p in prs.part.package.iter_parts()}
    report = []
    for path in map(Path, font_paths):
        font = TTFont(path)
        full = _name(font, 4)
        ribbi = _name(font, 2).lower() in ("regular", "bold", "italic", "bold italic")
        # A non-RIBBI weight (SemiBold, ExtraBold) is addressed by its full name in decks, even when
        # the font calls every weight by the bare family name — so try the full name first.
        names = ([] if ribbi else [full]) + [_name(font, 1), _name(font, 16), full]
        hit = next((n for n in names if n and n.lower() in used), None)
        if hit is None:
            report.append(f"skip  {path.name}: deck never uses {names[0]!r}")
            continue
        typeface = used[hit.lower()]
        # A full-name match ("Lato Light Italic") means the deck names the style itself: regular slot.
        slot = "regular" if hit == full else _slot(font)
        try:
            blob = to_eot(path.read_bytes())
        except ValueError as e:
            report.append(f"skip  {path.name}: {e}")
            continue
        entry = next((e for e in lst if e.find(f"{{{P}}}font").get("typeface").lower() == typeface.lower()), None)
        if entry is None:
            entry = etree.SubElement(lst, f"{{{P}}}embeddedFont")
            etree.SubElement(entry, f"{{{P}}}font", typeface=typeface)
        if entry.find(f"{{{P}}}{slot}") is not None:
            report.append(f"keep  {typeface} {slot}: already embedded")
            continue
        n = 1
        while f"/ppt/fonts/font{n}.fntdata" in taken:
            n += 1
        name = f"/ppt/fonts/font{n}.fntdata"
        taken.add(name)
        rid = prs.part.relate_to(Part(PackURI(name), CT_FONT, prs.part.package, blob), RT_FONT)
        el = etree.Element(f"{{{P}}}{slot}", {f"{{{R}}}id": rid})
        later = [entry.find(f"{{{P}}}{s}") for s in SLOTS[SLOTS.index(slot) + 1:]]
        nxt = next((e for e in later if e is not None), None)
        nxt.addprevious(el) if nxt is not None else entry.append(el)
        report.append(f"embed {typeface} {slot} <- {path.name} ({len(blob) // 1024} KB)")
    prs.save(dst)
    return report


def _selftest():
    import tempfile
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef"])
    fb.setupCharacterMap({})
    pen = TTGlyphPen(None)
    fb.setupGlyf({".notdef": pen.glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Selftest Sans", "styleName": "Bold"})
    fb.setupOS2(fsSelection=0x20, usWeightClass=700)
    fb.setupPost()
    buf = io.BytesIO(); fb.save(buf)
    ttf = buf.getvalue()
    names, data = read_eot(to_eot(ttf))
    assert names[0] == "Selftest Sans" and names[1] == "Bold", names
    assert data == ttf
    assert _slot(TTFont(io.BytesIO(ttf))) == "bold"
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        _selftest()
    elif len(sys.argv) >= 4:
        for line in embed_fonts(sys.argv[1], sys.argv[2], sys.argv[3:]):
            print(line)
    else:
        sys.exit(__doc__)
