"""Download module — download files from URLs."""

import os
from pathlib import Path
from urllib.parse import urlparse

import requests

DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/app/data/downloads"))


def download_file(url: str, filename: str = "") -> str:
    """Download a file from a URL."""
    try:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not filename:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path) or "download"

        resp = requests.get(url, timeout=30, stream=True, headers={"User-Agent": "Agent/0.1"})
        resp.raise_for_status()

        filepath = DOWNLOAD_DIR / filename
        total = 0
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)

        size_kb = total / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:.1f} KB"

        return f"Downloaded: `{filename}` ({size_str})\nSaved to: `{filepath}`"

    except requests.RequestException as e:
        return f"Download failed: {e}"
    except Exception as e:
        return f"Error: {e}"


def list_downloads() -> str:
    """List downloaded files."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(DOWNLOAD_DIR.iterdir())
    if not files:
        return "No downloads yet."
    lines = []
    for f in files:
        if f.is_file():
            size = f.stat().st_size
            if size > 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{size / 1024:.1f} KB"
            lines.append(f"`{f.name}` — {size_str}")
    return "\n".join(lines) if lines else "No downloads yet."
