"""Mac Cleaner API — HTTP layer.

The interesting logic lives next door: `safety.py` decides which paths may be
read or trashed, and `scanner.py` measures the filesystem. This module is just
the transport, so the rules stay auditable and testable without a web server.

Safety posture: this process can move a user's files to the Trash, so it binds
to loopback only, accepts requests from local origins only, and validates every
inbound path against the allow-list before touching it. Deletion goes through
the macOS Trash API — nothing is destroyed outright.
"""

from __future__ import annotations

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from send2trash import send2trash

import safety
import scanner
from safety import Category, PathNotAllowed

app = FastAPI(title="Mac Cleaner API")

# The UI runs on Vite (5173, or 5174 when that port is taken), the preview
# server (4173), or a plain dev server on 3000. Nothing else has any business
# talking to this API, and a strict origin list means a page on the open
# internet cannot preflight its way into a delete request.
ALLOWED_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (5173, 5174, 4173, 3000)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


@app.middleware("http")
async def block_dns_rebinding(request: Request, call_next):
    """Reject requests whose Host header is not loopback.

    Without this a hostile site can point a domain it controls at 127.0.0.1 and
    reach the API from the browser with a same-origin Host header, sidestepping
    CORS entirely.
    """
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host and host not in LOOPBACK_HOSTS:
        return JSONResponse({"detail": "Unrecognized Host header"}, status_code=421)
    return await call_next(request)


cache = scanner.ResultCache()

ITEMS_PER_CATEGORY = 50
MAX_LARGE_FILES = 100
MAX_DUPLICATE_GROUPS = 200
MAX_DEV_ARTIFACTS = 200


def readable(raw: str) -> str:
    """Validate an inbound path, translating a refusal into an HTTP 403."""
    try:
        resolved = safety.resolve_readable(raw)
    except PathNotAllowed as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=404, detail="Directory not found or is not a directory")
    return resolved


@app.get("/api/health")
def health():
    return {"status": "ok", "home": safety.HOME}


@app.get("/api/system-info")
def get_system_info():
    usage = shutil.disk_usage("/")
    return {"total": usage.total, "used": usage.used, "free": usage.free}


@app.get("/api/scan")
def scan_junk(refresh: bool = False):
    """Size every known category, scanning the categories concurrently."""

    def run():
        present = [c for c in safety.CATEGORIES if os.path.isdir(c.path)]

        def scan_one(category: Category) -> Optional[Dict[str, Any]]:
            items = scanner.get_immediate_children(category.path)
            total = sum(item["sizeBytes"] for item in items)
            if total <= 0:
                return None
            # Probe with a child path: the category root itself is protected
            # from removal, but its contents may still be removable.
            probe = os.path.join(category.path, "probe")
            return {
                "category": category.name,
                "path": category.path,
                "safe": category.safe,
                "description": category.description,
                "deletable": safety.deletion_refusal(probe) is None,
                "totalSizeBytes": total,
                "itemCount": len(items),
                "items": items[:ITEMS_PER_CATEGORY],
            }

        with ThreadPoolExecutor(max_workers=min(scanner.MAX_WORKERS, max(1, len(present)))) as pool:
            results = [r for r in pool.map(scan_one, present) if r]

        results.sort(key=lambda r: r["totalSizeBytes"], reverse=True)
        return {"scanResults": results}

    return cache.get_or_compute("scan", run, refresh)


@app.get("/api/inspect")
def inspect_path(path: str, refresh: bool = False):
    resolved = readable(path)

    def run():
        items = scanner.get_immediate_children(resolved)
        return {
            "path": resolved,
            "totalSizeBytes": sum(item["sizeBytes"] for item in items),
            "items": items,
        }

    return cache.get_or_compute(f"inspect:{resolved}", run, refresh)


@app.get("/api/duplicates")
def scan_duplicates(path: str, min_size_mb: float = 1):
    resolved = readable(path)
    min_size_bytes = max(1, int(min_size_mb * 1024 * 1024))
    duplicates = scanner.find_duplicates(resolved, min_size_bytes)
    return {
        "path": resolved,
        "duplicateGroups": duplicates[:MAX_DUPLICATE_GROUPS],
        "groupCount": len(duplicates),
        "totalWastedBytes": sum(d["totalWastedBytes"] for d in duplicates),
    }


@app.get("/api/large-files")
def scan_large_files(path: str, min_size_mb: float = 50):
    resolved = readable(path)
    min_size_bytes = max(1, int(min_size_mb * 1024 * 1024))
    items, total = scanner.find_large_files(resolved, min_size_bytes)
    return {
        "path": resolved,
        "items": items[:MAX_LARGE_FILES],
        "itemCount": len(items),
        "totalSizeBytes": total,
    }


@app.get("/api/dev-artifacts")
def scan_dev_artifacts(path: str, min_size_mb: float = 10, refresh: bool = False):
    """Find regenerable build and dependency directories under a project folder.

    Never bulk-selectable: removing `node_modules` costs a reinstall, and only
    the person who owns the project knows whether that is convenient right now.
    """
    resolved = readable(path)
    min_size_bytes = max(0, int(min_size_mb * 1024 * 1024))

    def run():
        items, total = scanner.find_dev_artifacts(resolved, min_size_bytes)
        return {
            "path": resolved,
            "items": items[:MAX_DEV_ARTIFACTS],
            "itemCount": len(items),
            "totalSizeBytes": total,
        }

    return cache.get_or_compute(f"dev:{resolved}:{min_size_bytes}", run, refresh)


class CleanRequest(BaseModel):
    paths: List[str] = Field(..., min_length=1, max_length=5000)
    # Lets the UI show exactly what would go before anything actually moves.
    dry_run: bool = False


@app.post("/api/clean")
def clean_files(request: CleanRequest):
    """Move the requested paths to the Trash.

    Nothing is destroyed: send2trash uses the macOS Trash API, so every item
    stays restorable. The whole request is validated before the first move, and
    a path that fails validation is reported rather than silently skipped.
    """
    approved, errors = safety.plan_deletions(request.paths)
    planned: List[Dict[str, Any]] = [
        {"path": path, "sizeBytes": scanner.path_size(path)}
        for path in approved
        if os.path.lexists(path)  # already gone: nothing to do, nothing to report
    ]

    if request.dry_run:
        return {
            "success": not errors,
            "dryRun": True,
            "planned": planned,
            "deletedSizeBytes": sum(p["sizeBytes"] for p in planned),
            "errors": errors,
        }

    deleted_size = 0
    deleted_count = 0
    for item in planned:
        try:
            send2trash(item["path"])
        except OSError as exc:
            errors.append({"path": item["path"], "error": exc.strerror or str(exc)})
            continue
        except Exception as exc:  # send2trash raises bare exceptions on some failures
            errors.append({"path": item["path"], "error": str(exc)})
            continue
        deleted_size += item["sizeBytes"]
        deleted_count += 1

    cache.clear()
    return {
        "success": not errors,
        "deletedSizeBytes": deleted_size,
        "deletedCount": deleted_count,
        "errors": errors,
    }


if __name__ == "__main__":
    import uvicorn

    # Loopback only: this API can move files to the Trash and must never be
    # reachable from the local network.
    uvicorn.run(app, host=os.environ.get("MAC_CLEANER_HOST", "127.0.0.1"), port=8000)
