"""Open a folder in the system file manager (cross-platform, stdlib)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder_in_file_manager(path: Path) -> None:
    """Open `path` in Explorer / Finder / xdg-open. No-op if not a directory."""
    path = path.expanduser().resolve()
    if not path.is_dir():
        return
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
