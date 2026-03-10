"""Persist and retrieve snapshots to/from disk."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from rubicon.snapshot.models import Snapshot, dict_to_snapshot, snapshot_to_dict

SNAPSHOTS_DIR = ".rubicon_data/snapshots"


def save_snapshot(root: Path, snapshot: Snapshot) -> Path:
    """Write a snapshot to .rubicon/snapshots/{timestamp}.json.

    Creates the directory if needed. Returns the path to the saved file.
    """
    snapshots_dir = root / SNAPSHOTS_DIR
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    filename = snapshot.timestamp.strftime("%Y%m%dT%H%M%SZ") + ".json"
    file_path = snapshots_dir / filename

    data = snapshot_to_dict(snapshot)
    file_path.write_text(json.dumps(data, indent=2))

    return file_path


def load_snapshot(path: Path) -> Snapshot:
    """Load a snapshot from a specific JSON file."""
    data = json.loads(path.read_text())
    return dict_to_snapshot(data)


def load_latest_snapshot(root: Path) -> Snapshot | None:
    """Load the most recent snapshot, or None if no snapshots exist."""
    snapshots = list_snapshots(root)
    if not snapshots:
        return None
    return load_snapshot(snapshots[-1])


def list_snapshots(root: Path) -> list[Path]:
    """Return all snapshot files sorted by name (chronological)."""
    snapshots_dir = root / SNAPSHOTS_DIR
    if not snapshots_dir.is_dir():
        return []
    return sorted(snapshots_dir.glob("*.json"))


def get_commit_hash(root: Path) -> str | None:
    """Get the current git commit hash, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None
