"""Default qBittorrent ``nova3/engines`` paths.

Matches typical Qt AppLocalData / XDG layouts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_qbt_data_root() -> Path:
    """Return the default per-user qBittorrent data directory (parent of nova3)."""
    home = Path.home()
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else home / "AppData" / "Local"
        return base / "qBittorrent"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "qBittorrent"
    # Linux/*BSD: XDG_DATA_HOME or ~/.local/share; legacy …/data/qBittorrent
    xdg = os.environ.get("XDG_DATA_HOME")
    share = Path(xdg) if xdg else home / ".local" / "share"
    modern = share / "qBittorrent"
    legacy = share / "data" / "qBittorrent"
    if legacy.exists() and not modern.exists():
        return legacy
    return modern


def default_engines_dir() -> Path:
    return default_qbt_data_root() / "nova3" / "engines"
