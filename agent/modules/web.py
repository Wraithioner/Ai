"""Web fetching module."""

import requests


def fetch_url(url: str) -> str:
    """Fetch a URL and return its text content."""
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Agent/0.1"})
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" in content_type:
            return _extract_text(resp.text)
        return resp.text[:5000]
    except requests.RequestException as e:
        return f"Error fetching URL: {e}"


def _extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line for line in text.splitlines() if line.strip()]
        return "\n".join(lines[:100])
    except ImportError:
        return html[:5000]
