"""Parse Unofficial-search-plugins.mediawiki tables into plugin records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlparse

WIKI_URL = (
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/"
    "refs/heads/master/wiki/Unofficial-search-plugins.mediawiki"
)

_PY_URL_RE = re.compile(
    r"https?://[^\s\[\]<>\")]+(?:\.py)(?:[^\s\[\]<>\")#]*)?",
    re.IGNORECASE,
)


@dataclass
class PluginRow:
    """One row from the wiki (public or private table)."""

    category: Literal["public", "private"]
    title: str
    author_cell: str
    version: str
    comments: str
    download_urls: list[str]
    icon_url: str = ""


def extract_first_wikitable(section: str) -> str:
    """Return inner text of first `{| ... |}` block, including `{|` / `|}` markers."""
    start = section.find("{|")
    if start == -1:
        return ""
    depth = 0
    i = start
    n = len(section)
    while i < n:
        if section.startswith("{|", i):
            depth += 1
            i += 2
            continue
        if section.startswith("|}", i):
            depth -= 1
            i += 2
            if depth == 0:
                return section[start:i]
            continue
        i += 1
    return ""


def split_sections(text: str) -> tuple[str, str]:
    """Return (public_section, private_section) wiki text after headings."""
    pub_mark = "= Plugins for Public Sites ="
    priv_mark = "= Plugins for Private Sites ="
    i_pub = text.find(pub_mark)
    i_priv = text.find(priv_mark)
    if i_pub == -1:
        public = ""
    else:
        public = (
            text[i_pub + len(pub_mark) : i_priv]
            if i_priv != -1
            else text[i_pub + len(pub_mark) :]
        )
    if i_priv == -1:
        private = ""
    else:
        rest = text[i_priv + len(priv_mark) :]
        m = re.search(r"\n=[^=]", rest)
        private = rest[: m.start()] if m else rest
    return public, private


def _normalize_row_lines(row_block: str) -> list[str]:
    """Merge continuation lines into cells; cells start with `|` or `!` (header)."""
    lines = row_block.strip().splitlines()
    cells: list[str] = []
    buf = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") or stripped.startswith("!"):
            if buf:
                cells.append(buf)
            buf = stripped[1:].strip()
        else:
            if buf:
                buf += "\n" + line
            else:
                buf = line
    if buf:
        cells.append(buf)
    return cells


def _strip_outer_table_markup(table_wiki: str) -> str:
    """Remove `{| ... first line` and trailing `|}` from a wikitable."""
    s = table_wiki.strip()
    if s.startswith("{|"):
        nl = s.find("\n")
        s = s[nl + 1 :] if nl != -1 else ""
    s = s.rstrip()
    if s.endswith("|}"):
        s = s[: s.rfind("|}")].rstrip()
    return s


def _strip_row_leading_marker(chunk: str) -> str:
    """Remove leading ``|-`` from first chunk (rows split on newline-|-newline)."""
    chunk = chunk.strip()
    if chunk.startswith("|-\n") or chunk.startswith("|-\r\n"):
        chunk = chunk.split("\n", 1)[1] if "\n" in chunk else ""
    elif chunk.startswith("|-") and len(chunk) > 2:
        chunk = chunk[2:].lstrip()
    return chunk.strip()


def _split_table_rows(table_wiki: str) -> list[str]:
    """Split wikitable into row chunks (each starts after |-)."""
    inner = _strip_outer_table_markup(table_wiki)
    rows: list[str] = []
    for part in re.split(r"\n\|-\s*\n", inner):
        part = _strip_row_leading_marker(part)
        if not part:
            continue
        rows.append(part)
    return rows


def _strip_wiki_noise(s: str) -> str:
    """Lightweight cleanup for display (not full wiki parsing)."""
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _wiki_comments_plain(s: str, max_len: int = 2000) -> str:
    """Comments cell for tooltips: keep line breaks from <br>, trim noise."""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    lines = [_strip_wiki_noise(line) for line in s.splitlines()]
    lines = [ln for ln in lines if ln]
    out = "\n".join(lines).strip()
    return out[:max_len]


def plain_author_display(author_cell: str, max_len: int = 160) -> str:
    """Author column often contains [url Label]; show the label for list text."""
    s = _strip_wiki_noise(author_cell)
    if not s:
        return "unknown"
    labels = re.findall(r"\[https?://\S+\s+([^\]]+)\]", s)
    if labels:
        t = labels[-1].strip()
        return t[:max_len] if t else s[:max_len]
    t = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", s)
    t = _strip_wiki_noise(t)
    return (t or s)[:max_len]


def _title_from_engine_cell(cell: str) -> str:
    """Title from ``[url Title]``; prefer last match (favicon link is often first)."""
    cell = _strip_wiki_noise(cell)
    # Drop [[...]] icon markup so `]] [` does not glue into one bogus `\S+` span
    cell = re.sub(r"\[\[[^\]]*\]\]", "", cell)
    # URL has no spaces (\S+); then space; then title (allows spaces in title)
    parts = re.findall(r"\[https?://\S+\s+([^\]]+)\]", cell)
    for candidate in reversed(parts):
        c = candidate.strip()
        if len(c) > 1:
            return c[:200]
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", cell)
    t = re.sub(r"\[https?://[^\]\s]+\s+([^\]]+)\]", r"\1", t)
    return _strip_wiki_noise(t)[:200] or "unknown"


def _extract_icon_url(cell: str) -> str:
    """Get icon URL from first wiki image link in engine cell."""
    m = re.search(r"\[\[((?:https?:)?//[^\]|]+)", cell.strip())
    if not m:
        return ""
    url = m.group(1).strip()
    if url.startswith("//"):
        url = f"https:{url}"
    raw_asset = _github_blob_asset_to_raw(url)
    if raw_asset:
        url = raw_asset
    # Remove wiki artifacts and noisy trailing bits
    url = url.rstrip(")")
    return url


def _extract_py_urls(cell: str) -> list[str]:
    found = _PY_URL_RE.findall(cell)
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for u in found:
        # strip trailing punctuation wiki might glue
        u = u.rstrip(").,;]")
        u = unquote(u)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _github_blob_to_raw(url: str) -> str | None:
    """Best-effort: github.com/.../blob/branch/path -> raw.githubusercontent.com."""
    p = urlparse(url)
    if p.netloc != "github.com":
        return None
    parts = [x for x in p.path.split("/") if x]
    # user, repo, blob, branch, ...path
    if len(parts) < 5 or parts[2] != "blob":
        return None
    user, repo = parts[0], parts[1]
    branch = parts[3]
    path = "/".join(parts[4:])
    if not path.endswith(".py"):
        return None
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"


def _github_blob_asset_to_raw(url: str) -> str | None:
    """Best-effort: github blob asset URL -> raw.githubusercontent.com."""
    p = urlparse(url)
    if p.netloc != "github.com":
        return None
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 5 or parts[2] != "blob":
        return None
    user, repo = parts[0], parts[1]
    branch = parts[3]
    path = "/".join(parts[4:])
    return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"


def expand_download_urls(urls: list[str]) -> list[str]:
    """Add raw.github equivalent for blob URLs; keep order, de-dupe."""
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.strip()
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        raw = _github_blob_to_raw(u)
        if raw and raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def parse_wiki(text: str) -> tuple[list[PluginRow], list[PluginRow]]:
    public_sec, private_sec = split_sections(text)
    pub_table = extract_first_wikitable(public_sec)
    priv_table = extract_first_wikitable(private_sec)

    public_rows = _parse_table(pub_table, "public")
    private_rows = _parse_table(priv_table, "private")
    return public_rows, private_rows


def _parse_table(
    table_wiki: str, category: Literal["public", "private"]
) -> list[PluginRow]:
    if not table_wiki.strip():
        return []
    rows_raw = _split_table_rows(table_wiki)
    out: list[PluginRow] = []
    for block in rows_raw:
        cells = _normalize_row_lines(block)
        if not cells:
            continue
        # Header row: lines start with !
        if cells[0].lstrip().startswith("!") or "Search Engine" in cells[0]:
            continue
        if len(cells) < 5:
            continue
        # Skip header row
        if "search engine" in cells[0].lower() and "author" in cells[1].lower():
            continue
        engine, author, version, _, dl, *rest = (
            cells[0],
            cells[1],
            cells[2],
            cells[3],
            cells[4],
            *cells[5:],
        )
        comments = rest[0] if rest else ""
        title = _title_from_engine_cell(engine)
        icon_url = _extract_icon_url(engine)
        urls = expand_download_urls(_extract_py_urls(dl))
        out.append(
            PluginRow(
                category=category,
                title=title,
                author_cell=_strip_wiki_noise(author)[:300],
                version=_strip_wiki_noise(version)[:80],
                comments=_wiki_comments_plain(comments),
                download_urls=urls,
                icon_url=icon_url,
            )
        )
    return out
