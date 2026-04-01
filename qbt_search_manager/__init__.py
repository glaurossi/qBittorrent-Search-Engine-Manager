"""Qt (PySide6) GUI for the unofficial qBittorrent search plugin installer."""

from importlib.metadata import PackageNotFoundError, version


def _package_version() -> str:
    try:
        return version("qbt-search-manager")
    except PackageNotFoundError:
        return "0.1.0"


__version__ = _package_version()

APP_NAME_FULL = "qBittorrent Search Engine Manager"
APP_NAME_SHORT = "qBit SEM"
APP_ORG_NAME = "glaurossi"
APP_AUTHOR_DISPLAY = "Glau Rossi"
HELP_LINK_GITHUB = "https://github.com/glaurossi/qBittorrent-Search-Engine-Manager"
HELP_LINK_DONATE = "https://ko-fi.com/glaurossi"
