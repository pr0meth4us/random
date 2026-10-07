"""Move (or extract from zips) photos and videos taken within a month range.

The date comes from inside the file (EXIF in JPG/HEIC, QuickTime metadata in
MOV/MP4), not the filesystem date, which after a download or unzip is useless.
Files with no embedded date (screenshots, saved/received images) are left alone.

    python3 move_by_capture_date.py SRC_FOLDER DEST --from 2020-09 --to 2020-12            # dry run
    python3 move_by_capture_date.py SRC_FOLDER DEST --from 2020-09 --to 2020-12 --apply
    python3 move_by_capture_date.py A.zip B.zip DEST --from 2021-01 --by-month --apply     # extract only matches
    python3 move_by_capture_date.py --selftest

Only the top level of a folder (or of the folder inside a zip) is scanned.
--to defaults to open-ended. --by-month files into DEST/YYYY-MM/.
"""
import argparse
import collections
import os
import re
import shutil
import struct
import sys
import time
import zipfile
import zlib
from datetime import datetime, timedelta

IMAGE_EXTS = (".heic", ".jpg", ".jpeg", ".png")
VIDEO_EXTS = (".mov", ".mp4", ".m4v")
EXIF_DATE = re.compile(rb"((?:19|20)\d\d):([01]\d):([0-3]\d) [0-2]\d:[0-5]\d:[0-5]\d")
ISO_DATE = re.compile(rb"((?:19|20)\d\d)-([01]\d)-([0-3]\d)T[0-2]\d:[0-5]\d")
HEAD_BYTES = 512_000  # iPhone HEIC/JPG keep EXIF well inside this
BUSY_SECONDS = 120    # unzip sets the archive mtime when a file is done; a fresh mtime = still writing
COPY_CHUNK = 4 * 1024 * 1024
READ_ERRORS = (OSError, struct.error, zlib.error, EOFError, zipfile.BadZipFile)


def image_date(head):
    # ponytail: earliest EXIF date string ~= DateTimeOriginal (DateTime is the edit date, never earlier);
    # parse the EXIF IFD properly if that ever misfiles something.
    found = [m.group(1) + b"-" + m.group(2) + b"-" + m.group(3) for m in EXIF_DATE.finditer(head)]
    return min(found).decode() if found else None


def video_date(f, size):
    """Walk top-level atoms to moov. Seeks only forward, so a zip member stream works."""
    pos = 0
    while pos + 8 <= size:
        f.seek(pos)
        atom_size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if atom_size == 1:
            atom_size, header = struct.unpack(">Q", f.read(8))[0], 16
        elif atom_size == 0:
            atom_size = size - pos
        if atom_size < header:
            return None  # corrupt atom table
        if kind == b"moov":
            return moov_date(f.read(atom_size - header))
        pos += atom_size
    return None


def moov_date(moov):
    m = ISO_DATE.search(moov)  # com.apple.quicktime.creationdate, local time
    if m:
        return b"-".join(m.groups()).decode()
    i = moov.find(b"mvhd")
    if i < 0:
        return None
    version = moov[i + 4]
    seconds = struct.unpack(">Q", moov[i + 8:i + 16])[0] if version == 1 else struct.unpack(">I", moov[i + 8:i + 12])[0]
    return (datetime(1904, 1, 1) + timedelta(seconds=seconds)).strftime("%Y-%m-%d") if seconds else None


def stream_date(f, name, size):
    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXTS:
        return image_date(f.read(HEAD_BYTES))
    if ext in VIDEO_EXTS:
        return video_date(f, size)
    return None


def capture_date(path):
    with open(path, "rb") as f:
        return stream_date(f, path, os.fstat(f.fileno()).st_size)


def is_media(name):
    return not name.startswith("._") and name.lower().endswith(IMAGE_EXTS + VIDEO_EXTS)


def target(name, date, opts):
    """(destination path, None) if the file belongs in DEST, else (None, reason)."""
    if date is None:
        return None, "no date inside"
    if not opts.month_from <= date[:7] <= opts.month_to:
        return None, "outside range"
    folder = os.path.join(opts.dest, date[:7]) if opts.by_month else opts.dest
    return os.path.join(folder, name), None


def move_from_folder(src, opts, counts, months):
    for entry in sorted(os.scandir(src), key=lambda e: e.name):
        if not entry.is_file() or entry.name.startswith("._"):
            continue
        if not is_media(entry.name):
            counts["other types"] += 1
            continue
        if time.time() - entry.stat().st_mtime < BUSY_SECONDS:
            counts["still being written, skipped"] += 1
            continue
        try:
            date = capture_date(entry.path)
        except READ_ERRORS as e:
            print(f"  unreadable: {entry.name} ({e})", file=sys.stderr)
            counts["unreadable"] += 1
            continue
        path, reason = target(entry.name, date, opts)
        if reason is None and os.path.exists(path):
            reason = "name already in DEST"
        if reason:
            counts[reason] += 1
            continue
        months[date[:7]] += 1
        if opts.apply:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            shutil.move(entry.path, path)


def extract_from_zip(zip_path, opts, counts, months):
    try:
        zf = zipfile.ZipFile(zip_path)
    except READ_ERRORS as e:
        print(f"  skipping {zip_path}: {e.__class__.__name__} (damaged?)", file=sys.stderr)
        counts["damaged zips"] += 1
        return
    with zf:
        for info in zf.infolist():
            name = os.path.basename(info.filename)
            if info.is_dir() or info.filename.count("/") > 1 or not name or name.startswith("._"):
                continue
            if not is_media(name):
                counts["other types"] += 1
                continue
            try:
                with zf.open(info) as f:
                    date = stream_date(f, name, info.file_size)
                path, reason = target(name, date, opts)
                if reason is None and os.path.exists(path):
                    reason = "already extracted" if os.path.getsize(path) == info.file_size else "name already in DEST"
                if reason:
                    counts[reason] += 1
                    continue
                months[date[:7]] += 1
                if opts.apply:
                    extract_member(zf, info, path)
            except READ_ERRORS as e:
                print(f"  unreadable: {info.filename} ({e})", file=sys.stderr)
                counts["unreadable"] += 1


def extract_member(zf, info, path):
    # Write to a hidden .part then rename, so an interrupted run never leaves a truncated file under the real name.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".part")
    with zf.open(info) as src, open(part, "wb") as out:
        shutil.copyfileobj(src, out, COPY_CHUNK)
    stamp = time.mktime(info.date_time + (0, 0, -1))
    os.utime(part, (stamp, stamp))
    os.replace(part, path)


def run(opts):
    counts, months = collections.Counter(), collections.Counter()
    for src in opts.sources:
        before = sum(months.values())
        if os.path.isdir(src):
            move_from_folder(src, opts, counts, months)
        else:
            extract_from_zip(src, opts, counts, months)
        print(f"{os.path.basename(src)}: {sum(months.values()) - before} matched", flush=True)
    verb = ("moved" if os.path.isdir(opts.sources[0]) else "extracted") if opts.apply else "would take"
    print(f"{verb} {sum(months.values())} -> {opts.dest}")
    for month, n in sorted(months.items()):
        print(f"  {month}: {n}")
    for reason, n in sorted(counts.items()):
        print(f"{reason}: {n}")
    return counts, months


def selftest():
    import io
    import tempfile
    from types import SimpleNamespace

    exif = b"\xff\xd8junk2021:03:04 10:00:00 more 2020:10:05 09:30:00 end"
    assert image_date(exif) == "2020-10-05", "earliest EXIF date wins"
    assert image_date(b"no date here") is None
    iso_moov = b"....mvhd" + b"\x00" * 20 + b"com.apple.quicktime.creationdate2020-11-09T08:15:00+0700"
    assert moov_date(iso_moov) == "2020-11-09"
    seconds = int((datetime(2020, 12, 25) - datetime(1904, 1, 1)).total_seconds())
    mvhd_only = b"mvhd" + b"\x00" * 4 + struct.pack(">I", seconds) + b"\x00" * 8
    assert moov_date(mvhd_only) == "2020-12-25"
    moov = struct.pack(">I4s", 8 + len(iso_moov), b"moov") + iso_moov
    mov = struct.pack(">I4s", 16, b"ftyp") + b"qt  " * 2 + struct.pack(">I4s", 12, b"mdat") + b"\x00" * 4 + moov
    assert video_date(io.BytesIO(mov), len(mov)) == "2020-11-09", "walks past mdat to moov"

    with tempfile.TemporaryDirectory() as tmp:
        zpath = os.path.join(tmp, "t.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            new_jpg = b"\xff\xd8 2021:03:04 10:00:00 " + b"x" * 1000
            zf.writestr("album/new.jpg", new_jpg)
            zf.writestr("album/old.jpg", b"\xff\xd8 2020:05:01 10:00:00 ")
            zf.writestr("album/clip.mov", mov)
            zf.writestr("album/undated.jpg", b"\xff\xd8 nothing")
            zf.writestr("album/Lib.photoslibrary/deep.jpg", b"\xff\xd8 2022:01:01 10:00:00 ")
        dest = os.path.join(tmp, "out")
        opts = SimpleNamespace(sources=[zpath], dest=dest, month_from="2020-11", month_to="9999-12", by_month=True, apply=True)
        counts, months = run(opts)
        assert os.path.getsize(os.path.join(dest, "2021-03", "new.jpg")) == len(new_jpg)
        assert os.path.exists(os.path.join(dest, "2020-11", "clip.mov"))
        assert sorted(os.listdir(dest)) == ["2020-11", "2021-03"], "old, undated and nested files stay in the zip"
        assert counts["no date inside"] == 1 and counts["outside range"] == 1
        counts, months = run(opts)
        assert counts["already extracted"] == 2 and not months, "rerun is a no-op"
    print("selftest ok")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("paths", nargs="*", metavar="SRC... DEST", help="folder(s) or zip file(s), then the destination folder")
    p.add_argument("--from", dest="month_from", help="first month, YYYY-MM")
    p.add_argument("--to", dest="month_to", default="9999-12", help="last month, YYYY-MM (inclusive; default: no limit)")
    p.add_argument("--by-month", action="store_true", help="file into DEST/YYYY-MM/")
    p.add_argument("--apply", action="store_true", help="actually move/extract (default is a dry run)")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    month = re.compile(r"^\d{4}-\d{2}$")
    if len(a.paths) < 2 or not a.month_from or not (month.match(a.month_from) and month.match(a.month_to)):
        p.error("need SRC... DEST --from YYYY-MM [--to YYYY-MM]")
    a.sources, a.dest = a.paths[:-1], a.paths[-1]
    for src in a.sources:
        if not (os.path.isdir(src) or (os.path.isfile(src) and src.lower().endswith(".zip"))):
            p.error(f"not a folder or .zip: {src}")
    run(a)


if __name__ == "__main__":
    main()
