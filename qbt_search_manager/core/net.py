"""HTTP GET via urllib (stdlib)."""

from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from pathlib import Path


USER_AGENT = (
    "qbt-unofficial-plugin-tool/0.1 (+https://github.com/qbittorrent/search-plugins)"
)


def fetch_bytes(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{e.reason!r} for {url}") from e


def fetch_text(url: str, timeout: float = 60.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def download_file(url: str, dest: Path, timeout: float = 120.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"{e.reason!r} for {url}") from e
    dest.write_bytes(data)


def probe_url_status(url: str, timeout: float = 12.0) -> str:
    """Return basic reachability status: ok|timeout|unreachable."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx):
            return "ok"
    except urllib.error.HTTPError as e:
        # Some hosts block HEAD but are reachable via GET.
        if e.code in {400, 401, 403, 405}:
            pass
        else:
            return "unreachable"
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            return "timeout"
        return "unreachable"

    # Fallback probe: tiny GET when HEAD is disallowed.
    get_req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
    )
    try:
        with urllib.request.urlopen(get_req, timeout=timeout, context=ctx):
            return "ok"
    except urllib.error.HTTPError as e:
        return "ok" if e.code == 416 else "unreachable"
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            return "timeout"
        return "unreachable"
