<h1 align="center">qBittorrent Search Engine Manager</h1>
<div align="center">
  <img src="https://www.glaurossi.com/assets/qbitsem.jpg"  />
</div>

## A desktop utility to manage [unofficial qBittorrent search plugins](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins).

### Requirements

- Python 3.10+
- PySide6
- qBittorrent

### Installation

```bash
git clone https://github.com/glaurossi/qBittorrent-Search-Engine-Manager
cd qBittorrent-Search-Engine-Manager
python -m pip install .
```

### Usage

*Already know how qBittorrent search plugins work? Skip to step 3.*

1. Open qBittorrent at least once -- this will create your profile/data folders.
2. Then go to **Search** → **Search plugins...** and **Check for updates**, so the engine setup is initialized.
3. Run the app:

```bash
python -m qbt_search_manager
```

### Notes
> [!CAUTION]
> Review engine source before using it, and avoid plugins that look suspicious or include behavior you do not trust.
- Engines are community-maintained scripts; quality and availability vary.
- For private engines, follow each engine author's setup instructions after install.

### To-do

- [ ]  A proper logo
- [ ]  Validate behaviour on **Linux**.
- [ ]  Ship **standalone builds** for **macOS**, **Windows**, and **Linux**
- [ ]  Improve **docs** for weird cases like custom qBittorrent profiles, proxies, SSL/certificate setup on fresh Python installs.

### Contributions
Any improvements, bug fixes, or feature additions are welcome. Feel free to do so by [submitting a PR](https://github.com/glaurossi/qBittorrent-Search-Engine-Manager/pulls).

### Issues

Found a bug or have a feature request? [Open an issue](https://github.com/glaurossi/qBittorrent-Search-Engine-Manager/issues).

<h2 align="left">Star History</h2>
<p align="center">
  <a href="https://www.star-history.com/#glaurossi/qBittorrent-Search-Engine-Manager">
    <img src="https://api.star-history.com/svg?repos=glaurossi/qBittorrent-Search-Engine-Manager" alt="Star History Chart" width="800">
  </a>
</p>

### License

MIT — see [LICENSE](LICENSE).
