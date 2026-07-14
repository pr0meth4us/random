import os
import shutil
import hashlib
import time
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

app = FastAPI(title="Mac Cleaner API")

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define target directories
HOME = str(Path.home())
TARGET_DIRS = {
    "User Caches": os.path.join(HOME, "Library", "Caches"),
    # Adding some specific caches to show more granular results
    "NPM Cache": os.path.join(HOME, ".npm", "_cacache"),
    "Pip Cache": os.path.join(HOME, ".cache", "pip")
}

def get_dir_size(path: str) -> int:
    """Return total size of a directory in bytes."""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(entry.path)
    except PermissionError:
        pass
    except FileNotFoundError:
        pass
    return total

def get_immediate_subdirs(path: str) -> List[Dict[str, Any]]:
    """Get size of immediate subdirectories to treat them as 'apps/items'."""
    items = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                size = 0
                if entry.is_dir(follow_symlinks=False):
                    size = get_dir_size(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                
                if size > 0:
                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "sizeBytes": size
                    })
    except PermissionError:
        pass
    except FileNotFoundError:
        pass
    
    # Sort by size descending
    items.sort(key=lambda x: x["sizeBytes"], reverse=True)
    return items

@app.get("/api/system-info")
def get_system_info():
    usage = shutil.disk_usage("/")
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free
    }

@app.get("/api/scan")
def scan_junk():
    results = []
    
    for category, path in TARGET_DIRS.items():
        if os.path.exists(path):
            items = get_immediate_subdirs(path)
            total_size = sum(item["sizeBytes"] for item in items)
            if total_size > 0:
                results.append({
                    "category": category,
                    "path": path,
                    "totalSizeBytes": total_size,
                    "items": items[:50] # Limit to top 50 largest items per category for UI performance
                })
    
    return {"scanResults": results}

@app.get("/api/inspect")
def inspect_path(path: str):
    # Expand ~ if present
    path = os.path.expanduser(path)
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Directory not found or is not a directory")
    
    items = get_immediate_subdirs(path)
    total_size = sum(item["sizeBytes"] for item in items)
    
    return {
        "path": path,
        "totalSizeBytes": total_size,
        "items": items
    }

def hash_file(path: str, block_size=65536) -> str:
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
    except Exception:
        return ""
    return hasher.hexdigest()

@app.get("/api/duplicates")
def scan_duplicates(path: str, min_size_mb: int = 1):
    path = os.path.expanduser(path)
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Directory not found or is not a directory")
        
    min_size_bytes = min_size_mb * 1024 * 1024
    
    # 1. Group by size
    size_map = defaultdict(list)
    try:
        for root, _, files in os.walk(path):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    if os.path.islink(filepath):
                        continue
                    size = os.path.getsize(filepath)
                    if size >= min_size_bytes:
                        size_map[size].append(filepath)
                except Exception:
                    pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    # 2. Hash files that share the same size
    duplicates = []
    for size, paths in size_map.items():
        if len(paths) > 1:
            hash_map = defaultdict(list)
            for p in paths:
                file_hash = hash_file(p)
                if file_hash:
                    hash_map[file_hash].append(p)
                    
            for file_hash, identical_paths in hash_map.items():
                if len(identical_paths) > 1:
                    items = []
                    for p in identical_paths:
                        items.append({
                            "name": os.path.basename(p),
                            "path": p,
                            "sizeBytes": size
                        })
                    duplicates.append({
                        "hash": file_hash,
                        "sizeBytes": size,
                        "totalWastedBytes": size * (len(identical_paths) - 1),
                        "items": items
                    })
                    
    duplicates.sort(key=lambda x: x["totalWastedBytes"], reverse=True)
    
    return {
        "path": path,
        "duplicateGroups": duplicates,
        "totalWastedBytes": sum(d["totalWastedBytes"] for d in duplicates)
    }

@app.get("/api/large-files")
def scan_large_files(path: str, min_size_mb: int = 50):
    path = os.path.expanduser(path)
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Directory not found or is not a directory")
        
    min_size_bytes = min_size_mb * 1024 * 1024
    large_files = []
    target_extensions = {".dmg", ".pkg", ".zip", ".iso"}
    
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    if os.path.islink(filepath):
                        continue
                    size = os.path.getsize(filepath)
                    _, ext = os.path.splitext(file)
                    
                    if size >= min_size_bytes or (ext.lower() in target_extensions and size >= 10 * 1024 * 1024):
                        large_files.append({
                            "name": file,
                            "path": filepath,
                            "sizeBytes": size,
                            "extension": ext.lower()
                        })
                except Exception:
                    pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    large_files.sort(key=lambda x: x["sizeBytes"], reverse=True)
    total_wasted = sum(f["sizeBytes"] for f in large_files)
    
    return {
        "path": path,
        "items": large_files[:100],  # Limit to top 100 to avoid UI lag
        "totalSizeBytes": total_wasted
    }

class CleanRequest(BaseModel):
    paths: List[str]

@app.post("/api/clean")
def clean_files(request: CleanRequest):
    deleted_size = 0
    errors = []
    
    for path in request.paths:
        try:
            if not os.path.exists(path):
                continue
                
            size = 0
            if os.path.isfile(path):
                size = os.path.getsize(path)
            elif os.path.isdir(path):
                size = get_dir_size(path)
                
            # Safely move to Trash using native macOS Trash API
            from send2trash import send2trash
            send2trash(path)
            
            deleted_size += size
        except Exception as e:
            errors.append({"path": path, "error": str(e)})
            
    return {
        "success": len(errors) == 0,
        "deletedSizeBytes": deleted_size,
        "errors": errors
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
