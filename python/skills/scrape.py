"""Scrape a webpage and extract readable text."""

import sys
import urllib.request
import urllib.error
import re


def strip_html(html: str) -> str:
    """Remove HTML tags and extract text."""
    html = re.sub(r'<script[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: scrape.py <url>")
        return

    url = sys.argv[1]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Atlas/0.2"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > 5_000_000:
                print("Page too large (>5MB).")
                return
            html = resp.read(5_000_000).decode("utf-8", errors="replace")

        text = strip_html(html)

        # Get title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = strip_html(title_match.group(1)).strip() if title_match else "No title"

        print(f"Title: {title}\n")
        print(text[:4000])

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
