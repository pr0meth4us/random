"""Filesystem measurement: sizes, duplicates, and large files.

Every routine here does one pass over the tree and reuses the stat data the
directory listing already produced, rather than re-stat'ing each path. Hard
links are counted once, since two names for one inode occupy space once.
"""

from __future__ import annotations

import hashlib
import os
import stat
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

# On a real machine most walk errors just mean "not ours to look at" — a
# permission wall, or a cache file deleted while we were reading the directory.
# They are expected in bulk and are not worth surfacing.
_SKIPPABLE = OSError

MAX_WORKERS = 8


def iter_entries(root: str, skip_hidden: bool = False) -> Iterator[os.DirEntry]:
    """Yield every file entry under `root`, iteratively, never following symlinks.

    Iterative so a deep tree cannot exhaust the stack, and it yields `DirEntry`
    objects so callers can use the cached stat instead of paying another syscall.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if skip_hidden and entry.name.startswith("."):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            yield entry
                    except _SKIPPABLE:
                        continue
        except _SKIPPABLE:
            continue


def get_dir_size(path: str) -> int:
    """Total bytes under `path`, counting each hard-linked inode once."""
    total = 0
    seen: Set[Tuple[int, int]] = set()
    for entry in iter_entries(path):
        try:
            st = entry.stat(follow_symlinks=False)
        except _SKIPPABLE:
            continue
        if st.st_nlink > 1:
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
        total += st.st_size
    return total


def path_size(path: str) -> int:
    """Size of a file or directory, whichever `path` happens to be."""
    try:
        st = os.lstat(path)
    except _SKIPPABLE:
        return 0
    if stat.S_ISDIR(st.st_mode):
        return get_dir_size(path)
    return st.st_size


def get_immediate_children(path: str) -> List[Dict[str, Any]]:
    """Size each immediate child of `path`, sizing subdirectories in parallel.

    Cache trees are dominated by I/O wait, so fanning the per-child walks across
    threads turns a serial scan of dozens of cache folders into roughly one
    folder's worth of wall time.
    """
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except _SKIPPABLE:
        return []

    dirs: List[os.DirEntry] = []
    items: List[Dict[str, Any]] = []
    for entry in entries:
        try:
            if entry.is_dir(follow_symlinks=False):
                dirs.append(entry)
            elif entry.is_file(follow_symlinks=False):
                size = entry.stat(follow_symlinks=False).st_size
                if size > 0:
                    items.append({"name": entry.name, "path": entry.path, "sizeBytes": size})
        except _SKIPPABLE:
            continue

    if dirs:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(dirs))) as pool:
            for entry, size in zip(dirs, pool.map(lambda e: get_dir_size(e.path), dirs)):
                if size > 0:
                    items.append({"name": entry.name, "path": entry.path, "sizeBytes": size})

    items.sort(key=lambda x: x["sizeBytes"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------
_SAMPLE_BYTES = 64 * 1024
_HASH_CHUNK = 1024 * 1024
# blake2b is markedly faster than md5 on 64-bit CPUs. The digest only ever
# proves two files are byte-identical, so 128 bits is ample.
_HASHER = lambda: hashlib.blake2b(digest_size=16)  # noqa: E731


def sample_hash(path: str, size: int) -> str:
    """Cheap fingerprint from the head and tail of a file.

    Files of equal size that differ almost always differ within the first or
    last 64 KB, so this rules out most candidates after reading 128 KB instead
    of gigabytes.
    """
    hasher = _HASHER()
    try:
        with open(path, "rb") as f:
            hasher.update(f.read(_SAMPLE_BYTES))
            if size > 2 * _SAMPLE_BYTES:
                f.seek(-_SAMPLE_BYTES, os.SEEK_END)
                hasher.update(f.read(_SAMPLE_BYTES))
    except OSError:
        return ""
    return hasher.hexdigest()


def full_hash(path: str, _size: int = 0) -> str:
    hasher = _HASHER()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_HASH_CHUNK), b""):
                hasher.update(chunk)
    except OSError:
        return ""
    return hasher.hexdigest()


Candidate = Tuple[str, int]


def _group_by_digest(items: List[Candidate], hash_fn: Callable[[str, int], str]) -> Dict[str, List[Candidate]]:
    groups: Dict[str, List[Candidate]] = defaultdict(list)
    if not items:
        return groups
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        digests = pool.map(lambda item: hash_fn(item[0], item[1]), items)
        for item, digest in zip(items, digests):
            if digest:
                groups[digest].append(item)
    return groups


def find_duplicates(root: str, min_size_bytes: int) -> List[Dict[str, Any]]:
    """Find groups of byte-identical files, cheapest test first.

    Three passes, each narrowing the field: size, then a head/tail sample, then
    a full read. Only the survivors of each pass pay for the next one.
    """
    size_map: Dict[int, List[Candidate]] = defaultdict(list)
    seen_inodes: Set[Tuple[int, int]] = set()
    for entry in iter_entries(root):
        try:
            st = entry.stat(follow_symlinks=False)
        except _SKIPPABLE:
            continue
        if st.st_size < min_size_bytes:
            continue
        # Hard links and APFS clones share an inode, so extra names for them
        # cost nothing and deleting one reclaims nothing. Count each inode once.
        if st.st_nlink > 1:
            key = (st.st_dev, st.st_ino)
            if key in seen_inodes:
                continue
            seen_inodes.add(key)
        size_map[st.st_size].append((entry.path, st.st_size))

    candidates = [item for group in size_map.values() if len(group) > 1 for item in group]
    if not candidates:
        return []

    sampled = _group_by_digest(candidates, sample_hash)
    finalists = [item for group in sampled.values() if len(group) > 1 for item in group]
    confirmed = _group_by_digest(finalists, full_hash)

    duplicates = []
    for digest, group in confirmed.items():
        if len(group) < 2:
            continue
        size = group[0][1]
        duplicates.append({
            "hash": digest,
            "sizeBytes": size,
            "totalWastedBytes": size * (len(group) - 1),
            "items": [
                {"name": os.path.basename(p), "path": p, "sizeBytes": size}
                for p, _ in sorted(group)
            ],
        })

    duplicates.sort(key=lambda d: d["totalWastedBytes"], reverse=True)
    return duplicates


# ---------------------------------------------------------------------------
# Large files
# ---------------------------------------------------------------------------
# Installers and archives are worth flagging well below the general threshold:
# they are almost always re-downloadable and rarely needed after use.
INSTALLER_EXTENSIONS = {".dmg", ".pkg", ".iso", ".zip", ".tar", ".gz", ".xz", ".7z"}
INSTALLER_MIN_BYTES = 10 * 1024 * 1024


def find_large_files(root: str, min_size_bytes: int) -> Tuple[List[Dict[str, Any]], int]:
    """Return large files (sorted, largest first) and their combined size."""
    found: List[Dict[str, Any]] = []
    total = 0
    for entry in iter_entries(root, skip_hidden=True):
        try:
            st = entry.stat(follow_symlinks=False)
        except _SKIPPABLE:
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        if st.st_size >= min_size_bytes or (
            ext in INSTALLER_EXTENSIONS and st.st_size >= INSTALLER_MIN_BYTES
        ):
            found.append({
                "name": entry.name,
                "path": entry.path,
                "sizeBytes": st.st_size,
                "extension": ext,
            })
            total += st.st_size
    found.sort(key=lambda f: f["sizeBytes"], reverse=True)
    return found, total


# ---------------------------------------------------------------------------
# Result cache
# ---------------------------------------------------------------------------
class ResultCache:
    """Short-lived memo for scans.

    A full category scan touches millions of inodes; switching tabs in the UI
    should not pay that cost again. Entries expire quickly so the numbers never
    drift far from reality, and callers can force a refresh.
    """

    def __init__(self, ttl_seconds: float = 60, max_entries: int = 64):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: Dict[str, Tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_compute(self, key: str, produce: Callable[[], Any], refresh: bool = False) -> Any:
        if not refresh:
            with self._lock:
                hit = self._entries.get(key)
            if hit and time.monotonic() - hit[0] < self._ttl:
                return hit[1]
        value = produce()
        with self._lock:
            if len(self._entries) >= self._max:
                oldest = min(self._entries, key=lambda k: self._entries[k][0])
                self._entries.pop(oldest, None)
            self._entries[key] = (time.monotonic(), value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
