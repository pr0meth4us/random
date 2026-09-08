"""Which paths this app may read, and which it may move to the Trash.

Kept free of web-framework imports so the rules can be tested and audited on
their own — they are the part of the cleaner that matters most if it is wrong.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

HOME = os.path.realpath(str(Path.home()))


def home_path(*parts: str) -> str:
    return os.path.join(HOME, *parts)


class PathNotAllowed(Exception):
    """A client-supplied path falls outside what this app may touch."""


# Directories that may be read/browsed. Everything else is off limits, which
# keeps "Space Lens" from becoming an arbitrary filesystem reader.
READ_ROOTS: Tuple[str, ...] = tuple(
    p for p in (HOME, "/Applications", "/Library/Caches") if os.path.isdir(p)
)

# Deletion is narrower still: only inside the user's own home directory.
DELETE_ROOTS: Tuple[str, ...] = (HOME,)

# Exact directories that may be emptied but never removed — deleting the
# container itself breaks macOS or the user's account layout.
PROTECTED_EXACT: Set[str] = {
    "/",
    HOME,
    *(
        home_path(name)
        for name in (
            "Library", "Documents", "Desktop", "Downloads", "Pictures",
            "Movies", "Music", "Applications", "Public", "Sites",
        )
    ),
    home_path("Library", "Caches"),
    home_path("Library", "Logs"),
    home_path(".Trash"),
    home_path(".npm"),
    home_path(".cache"),
}

# Nothing at or below these may be deleted: credentials, keychains, app state
# that does not regenerate, and the iCloud mirror (deleting there deletes from
# every one of the user's devices).
PROTECTED_SUBTREES: Tuple[str, ...] = tuple(
    home_path(*parts)
    for parts in (
        (".ssh",), (".gnupg",), (".aws",), (".config",), (".kube",),
        (".docker", "config.json"), (".password-store",),
        ("Library", "Keychains"), ("Library", "Preferences"),
        ("Library", "Mobile Documents"), ("Library", "Containers"),
        ("Library", "Group Containers"), ("Library", "Application Support"),
        ("Library", "CloudStorage"),
    )
)


def is_within(path: str, root: str) -> bool:
    """True if `path` is `root` or lives under it, without string-prefix traps.

    `/home/u/Documents-other` must not read as being inside `/home/u/Documents`.
    """
    if path == root:
        return True
    return path.startswith(root.rstrip(os.sep) + os.sep)


def resolve_readable(raw: str) -> str:
    """Resolve a client-supplied path and confirm it sits in a readable root.

    Symlinks are resolved *before* the check, so `~/link-to-slash` cannot be
    used to walk out of the allow-list.
    """
    if not raw or not raw.strip():
        raise PathNotAllowed("A path is required")
    resolved = os.path.realpath(os.path.expanduser(raw.strip()))
    if not any(is_within(resolved, root) for root in READ_ROOTS):
        raise PathNotAllowed(
            "That folder is outside the areas this app is allowed to read."
        )
    return resolved


def deletion_refusal(path: str) -> Optional[str]:
    """Return why `path` may not be deleted, or None when it is allowed."""
    if not any(is_within(path, root) for root in DELETE_ROOTS):
        return "Outside your home folder"
    if path in PROTECTED_EXACT:
        return "This folder is part of your account layout and cannot be removed"
    for guarded in PROTECTED_SUBTREES:
        if is_within(path, guarded):
            return "Protected location (credentials, app data, or iCloud)"
    return None


def drop_nested(paths: List[str]) -> List[str]:
    """Remove paths already covered by an ancestor in the same request.

    Trashing a parent and then its child means the child is gone by the time we
    reach it, and naively summing both sizes double-counts what was reclaimed.
    """
    kept: List[str] = []
    for path in sorted(set(paths)):
        if kept and is_within(path, kept[-1]):
            continue
        kept.append(path)
    return kept


def plan_deletions(raw_paths: List[str]) -> Tuple[List[str], List[dict]]:
    """Resolve, validate and de-duplicate a batch of deletion requests.

    Validation runs *before* de-nesting, and that order matters: if a refused
    ancestor were collapsed first it would silently swallow the permitted paths
    beneath it, and the user's selection would quietly do nothing.
    """
    allowed: List[str] = []
    errors: List[dict] = []
    for raw in raw_paths:
        path = os.path.realpath(os.path.expanduser(raw))
        refusal = deletion_refusal(path)
        if refusal:
            errors.append({"path": path, "error": refusal})
        else:
            allowed.append(path)
    return drop_nested(allowed), errors


@dataclass(frozen=True)
class Category:
    """A scan target.

    `safe` marks caches that regenerate on their own — only those are offered
    for one-click bulk selection. Everything else is browse-and-choose.
    """

    name: str
    path: str
    safe: bool
    description: str


# Categories nested inside another entry's path are deliberately absent: the
# Homebrew, Yarn and go-build caches all live under ~/Library/Caches and already
# appear as items of "User Caches". Listing them twice double-counts the total.
CATEGORIES: Tuple[Category, ...] = (
    Category("User Caches", home_path("Library", "Caches"), True,
             "Application caches macOS rebuilds on demand."),
    Category("Trash", home_path(".Trash"), True,
             "Items already in the Trash."),
    Category("Xcode Derived Data", home_path("Library", "Developer", "Xcode", "DerivedData"), True,
             "Build intermediates Xcode regenerates."),
    Category("Xcode Device Support", home_path("Library", "Developer", "Xcode", "iOS DeviceSupport"), True,
             "Symbols for iOS versions you may no longer debug."),
    Category("Xcode Archives", home_path("Library", "Developer", "Xcode", "Archives"), False,
             "Shipped app archives — needed to symbolicate old crashes."),
    Category("NPM Cache", home_path(".npm", "_cacache"), True,
             "npm package cache."),
    Category("Pip Cache", home_path(".cache", "pip"), True,
             "pip wheel and download cache."),
    Category("uv Cache", home_path(".cache", "uv"), True,
             "uv package cache."),
    Category("Cargo Registry", home_path(".cargo", "registry"), True,
             "Rust crate sources; re-downloaded on build."),
    Category("Gradle Cache", home_path(".gradle", "caches"), True,
             "Gradle dependency and build cache."),
    Category("Maven Repository", home_path(".m2", "repository"), True,
             "Maven artifacts; re-downloaded on build."),
    Category("pnpm Store", home_path("Library", "pnpm", "store"), False,
             "pnpm content store — clearing it breaks hard-linked node_modules."),
    Category("Docker Data", home_path("Library", "Containers", "com.docker.docker", "Data"), False,
             "Docker VM disk — prune from Docker itself, not here."),
    Category("Downloads", home_path("Downloads"), False,
             "Your downloads. Review individually."),
    Category("Documents", home_path("Documents"), False,
             "Personal documents. Review individually."),
    Category("User Applications", home_path("Applications"), False,
             "Apps installed for your user only."),
    Category("System Applications", "/Applications", False,
             "Installed apps (read-only here)."),
)
