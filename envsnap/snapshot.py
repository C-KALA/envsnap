# snapshot.py — handles serialising captured environment data into a versioned JSON snapshot file and reading snapshots back from disk.

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

def save_snapshot(data: dict[str, Any], project_root: Path) -> Path | None:
    """
    Saves environment snapshot data to a JSON file.
    Creates .envsnap/snapshots/ inside project_root if it doesn't exist.
    Filename is YYYY-MM-DD_HH-MM.snapshot.
    Also updates .envsnap/current.snapshot with the same data.
    """
    try:
        envsnap_dir = project_root / ".envsnap"
        snapshots_dir = envsnap_dir / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp_str}.snapshot"
        snapshot_path = snapshots_dir / filename
        
        # Format JSON with 2 space indentation
        json_data = json.dumps(data, indent=2)
        
        with snapshot_path.open("w", encoding="utf-8") as f:
            f.write(json_data)
            
        current_path = envsnap_dir / "current.snapshot"
        with current_path.open("w", encoding="utf-8") as f:
            f.write(json_data)
            
        return snapshot_path
    except Exception:
        return None

def load_snapshot(snapshot_path: Path) -> dict[str, Any] | None:
    """
    Reads a .snapshot file and returns it as a dictionary.
    Handles file not found and invalid JSON gracefully.
    """
    try:
        if not snapshot_path.is_file():
            return None
        with snapshot_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def list_snapshots(project_root: Path) -> list[dict[str, Any]]:
    """
    Returns a list of all .snapshot files in .envsnap/snapshots/.
    Sorted newest first.
    Each item in the list is a dict with filename, timestamp, and full_path.
    """
    snapshots = []
    try:
        snapshots_dir = project_root / ".envsnap" / "snapshots"
        if not snapshots_dir.is_dir():
            return snapshots
            
        for file_path in snapshots_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".snapshot":
                try:
                    # Attempt to parse datetime from filename: YYYY-MM-DD_HH-MM
                    basename = file_path.stem
                    timestamp = datetime.strptime(basename, "%Y-%m-%d_%H-%M")
                    snapshots.append({
                        "filename": file_path.name,
                        "timestamp": timestamp,
                        "full_path": str(file_path.absolute())
                    })
                except ValueError:
                    # If filename doesn't match expected format, use modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    snapshots.append({
                        "filename": file_path.name,
                        "timestamp": mtime,
                        "full_path": str(file_path.absolute())
                    })
                    
        # Sort newest first based on timestamp
        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
    except Exception:
        pass
        
    return snapshots

def get_current_snapshot(project_root: Path) -> dict[str, Any] | None:
    """
    Reads and returns the data from .envsnap/current.snapshot.
    Returns None if the file doesn't exist or is invalid.
    """
    current_path = project_root / ".envsnap" / "current.snapshot"
    return load_snapshot(current_path)
