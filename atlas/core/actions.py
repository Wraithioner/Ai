"""Actions module - gives Atlas hands to control the computer."""

import logging
import os
import platform
import re
import subprocess
import sys
import webbrowser
from datetime import datetime

logger = logging.getLogger(__name__)

# Common app names mapped to how to launch them on Windows
WINDOWS_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "terminal": "cmd.exe",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "control panel": "control.exe",
    "snipping tool": "snippingtool.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "spotify": "spotify",
    "discord": "discord",
    "steam": "steam",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
}

# Common website shortcuts
WEBSITE_SHORTCUTS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "chatgpt": "https://chat.openai.com",
    "linkedin": "https://www.linkedin.com",
}


class Actions:
    """Parses user commands and executes system actions."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"

    def try_handle(self, text: str) -> tuple[bool, str | None]:
        """
        Try to parse and execute an action from the user's text.

        Returns:
            (handled, response) — if handled is True, response is what to say.
            If handled is False, the text should go to the LLM instead.
        """
        lower = text.lower().strip()

        # --- "open [something]" ---
        match = re.match(r"^(?:open|launch|start|run)\s+(.+)", lower)
        if match:
            target = match.group(1).strip()
            return self._handle_open(target, text)

        # --- "go to [url]" ---
        match = re.match(r"^(?:go to|navigate to|visit)\s+(.+)", lower)
        if match:
            target = match.group(1).strip()
            return self._handle_url(target)

        # --- "search for [query]" / "google [query]" ---
        match = re.match(r"^(?:search|search for|google|look up)\s+(.+)", lower)
        if match:
            query = match.group(1).strip()
            return self._handle_search(query)

        # --- "close [app]" ---
        match = re.match(r"^(?:close|kill|stop|end)\s+(.+)", lower)
        if match:
            target = match.group(1).strip()
            return self._handle_close(target)

        # --- "what time is it" ---
        if re.search(r"what(?:'s| is) the time|what time is it|tell me the time", lower):
            now = datetime.now().strftime("%I:%M %p")
            return True, f"It's {now}."

        # --- "what's the date" ---
        if re.search(r"what(?:'s| is) the date|what(?:'s| is) today|tell me the date", lower):
            today = datetime.now().strftime("%A, %B %d, %Y")
            return True, f"Today is {today}."

        # Not an action
        return False, None

    def _handle_open(self, target: str, original_text: str) -> tuple[bool, str]:
        """Handle 'open [target]' commands."""
        # Check if it looks like a URL
        if self._looks_like_url(target):
            return self._handle_url(target)

        # Check website shortcuts
        for name, url in WEBSITE_SHORTCUTS.items():
            if target == name or target == f"the {name}":
                return self._open_url(url, name)

        # Check known apps
        for name, cmd in WINDOWS_APPS.items():
            if target == name or target == f"the {name}":
                return self._open_app(cmd, name)

        # Try partial matching (e.g., "open the chrome browser" matches "chrome")
        for name, cmd in WINDOWS_APPS.items():
            if name in target:
                return self._open_app(cmd, name)

        for name, url in WEBSITE_SHORTCUTS.items():
            if name in target:
                return self._open_url(url, name)

        # Unknown target — try opening it directly (might be a file path)
        return self._open_unknown(target)

    def _handle_url(self, target: str) -> tuple[bool, str]:
        """Handle URL navigation."""
        # Clean up common speech artifacts
        target = target.strip().rstrip(".")

        # Check website shortcuts first
        for name, url in WEBSITE_SHORTCUTS.items():
            if target == name or target == f"the {name}":
                return self._open_url(url, name)

        # Add https:// if missing
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        return self._open_url(target, target)

    def _handle_search(self, query: str) -> tuple[bool, str]:
        """Handle web search commands."""
        import urllib.parse
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        try:
            webbrowser.open(url)
            logger.info("Searching Google for: %s", query)
            return True, f"Searching for {query}."
        except Exception as e:
            logger.error("Failed to search: %s", e)
            return True, f"I couldn't search for that. {e}"

    def _handle_close(self, target: str) -> tuple[bool, str]:
        """Handle 'close [app]' commands."""
        if not self.is_windows:
            return True, "I can only close apps on Windows right now."

        # Map target to process name
        process_map = {
            "notepad": "notepad.exe",
            "calculator": "Calculator.exe",
            "calc": "Calculator.exe",
            "paint": "mspaint.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "spotify": "Spotify.exe",
            "discord": "Discord.exe",
        }

        proc_name = None
        for name, proc in process_map.items():
            if name in target:
                proc_name = proc
                break

        if not proc_name:
            return True, f"I don't know how to close {target}."

        try:
            subprocess.run(
                ["taskkill", "/IM", proc_name, "/F"],
                capture_output=True, timeout=5,
            )
            logger.info("Closed %s", proc_name)
            return True, f"Closed {target}."
        except Exception as e:
            logger.error("Failed to close %s: %s", target, e)
            return True, f"I couldn't close {target}."

    def _open_app(self, cmd: str, name: str) -> tuple[bool, str]:
        """Open an application."""
        try:
            if self.is_windows:
                os.startfile(cmd)
            else:
                subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Opened app: %s (%s)", name, cmd)
            return True, f"Opening {name}."
        except Exception as e:
            logger.error("Failed to open %s: %s", name, e)
            return True, f"I couldn't open {name}. It might not be installed."

    def _open_url(self, url: str, name: str) -> tuple[bool, str]:
        """Open a URL in the default browser."""
        try:
            webbrowser.open(url)
            logger.info("Opened URL: %s", url)
            return True, f"Opening {name}."
        except Exception as e:
            logger.error("Failed to open URL %s: %s", url, e)
            return True, f"I couldn't open {name}."

    def _open_unknown(self, target: str) -> tuple[bool, str]:
        """Try to open an unknown target (could be a file, folder, or app)."""
        try:
            if self.is_windows:
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Opened: %s", target)
            return True, f"Opening {target}."
        except Exception as e:
            logger.warning("Could not open '%s': %s", target, e)
            # Fall through to LLM instead of giving an error
            return False, None

    def _looks_like_url(self, text: str) -> bool:
        """Check if text looks like a URL or domain name."""
        url_patterns = [
            r"^https?://",
            r"^www\.",
            r"\.(com|org|net|io|dev|co|edu|gov|app|me|tv|gg)$",
            r"\.(com|org|net|io|dev|co|edu|gov|app|me|tv|gg)/",
        ]
        for pattern in url_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
