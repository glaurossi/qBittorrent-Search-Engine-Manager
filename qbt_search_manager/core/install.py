"""Download .py plugins and install into nova3/engines."""

from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from qbt_search_manager.core.net import download_file
from qbt_search_manager.core.wiki_parser import PluginRow


def strip_url_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def filename_from_url(url: str) -> str:
    path = urlparse(strip_url_fragment(url)).path
    name = path.rsplit("/", 1)[-1]
    return unquote(name) if name else "plugin.py"


def pick_download_url(urls: list[str]) -> str | None:
    """Prefer obvious raw hosts; otherwise first URL."""
    if not urls:
        return None
    cleaned = [strip_url_fragment(u) for u in urls]

    def score(u: str) -> int:
        s = 0
        if "raw.githubusercontent.com" in u:
            s += 10
        if "gist.githubusercontent.com" in u:
            s += 10
        if "codeberg.org" in u and "/raw/" in u:
            s += 10
        if "gitlab.com" in u and "/-/raw/" in u:
            s += 10
        if u.endswith(".py"):
            s += 1
        return s

    return max(cleaned, key=score)


def expected_dest_path(row: PluginRow, engines_dir: Path) -> Path | None:
    """Path where this wiki row installs (same rules as ``install_plugin``)."""
    url = pick_download_url(row.download_urls)
    if not url:
        return None
    dest_name = filename_from_url(url)
    if not dest_name.endswith(".py"):
        dest_name += ".py"
    return engines_dir / dest_name


def is_plugin_installed(row: PluginRow, engines_dir: Path) -> bool:
    p = expected_dest_path(row, engines_dir)
    return p is not None and p.is_file()


def install_plugin(row: PluginRow, engines_dir: Path, log: callable) -> None:
    """Download to temp file, then move into engines_dir. Raises on failure."""
    url = pick_download_url(row.download_urls)
    if not url:
        raise ValueError(f"No .py download URL found for {row.title!r}")

    engines_dir.mkdir(parents=True, exist_ok=True)
    dest_name = filename_from_url(url)
    if not dest_name.endswith(".py"):
        dest_name += ".py"
    final = engines_dir / dest_name

    with tempfile.TemporaryDirectory(prefix="qbt-plg-") as tmp:
        tdir = Path(tmp)
        tmp_file = tdir / dest_name
        log(f"Downloading {dest_name} …\n")
        download_file(url, tmp_file)
        data = tmp_file.read_bytes()
        if b"# VERSION:" not in data and b"def search" not in data:
            log("Note: file may not be a valid nova engine; saved anyway.\n")

        if final.exists():
            final.unlink()
        tmp_file.replace(final)

    log(f"Installed {dest_name}.\n")


def remove_installed_plugin(row: PluginRow, engines_dir: Path) -> Path:
    """Delete the installed ``.py`` for this row; return path. May raise ``OSError``."""
    p = expected_dest_path(row, engines_dir)
    if p is None:
        raise FileNotFoundError(
            "No install path for this plugin (missing download URL)."
        )
    if not p.is_file():
        raise FileNotFoundError(f"Not on disk: {p.name}")
    p.unlink()
    return p
