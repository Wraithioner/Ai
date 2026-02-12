"""Actions module - handles direct commands and system actions."""

import logging
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime

logger = logging.getLogger(__name__)

# Common app names mapped to how to launch them
APPS = {
    "notepad": "notepad.exe" if sys.platform == "win32" else "gedit",
    "calculator": "calc.exe" if sys.platform == "win32" else "gnome-calculator",
    "calc": "calc.exe" if sys.platform == "win32" else "gnome-calculator",
    "paint": "mspaint.exe" if sys.platform == "win32" else "gimp",
    "file explorer": "explorer.exe" if sys.platform == "win32" else "nautilus",
    "explorer": "explorer.exe" if sys.platform == "win32" else "nautilus",
    "files": "explorer.exe" if sys.platform == "win32" else "nautilus",
    "command prompt": "cmd.exe" if sys.platform == "win32" else "x-terminal-emulator",
    "cmd": "cmd.exe" if sys.platform == "win32" else "x-terminal-emulator",
    "terminal": "cmd.exe" if sys.platform == "win32" else "x-terminal-emulator",
    "powershell": "powershell.exe",
    "task manager": "taskmgr.exe" if sys.platform == "win32" else "gnome-system-monitor",
    "settings": "ms-settings:" if sys.platform == "win32" else "gnome-control-center",
    "control panel": "control.exe",
    "snipping tool": "snippingtool.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "chrome": "chrome" if sys.platform == "win32" else "google-chrome",
    "google chrome": "chrome" if sys.platform == "win32" else "google-chrome",
    "firefox": "firefox",
    "edge": "msedge" if sys.platform == "win32" else "microsoft-edge",
    "microsoft edge": "msedge" if sys.platform == "win32" else "microsoft-edge",
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

# Process names for closing apps (cross-platform)
PROCESS_NAMES = {
    "notepad": ("notepad.exe", "gedit"),
    "calculator": ("Calculator.exe", "gnome-calculator"),
    "calc": ("Calculator.exe", "gnome-calculator"),
    "paint": ("mspaint.exe", "gimp"),
    "chrome": ("chrome.exe", "google-chrome"),
    "google chrome": ("chrome.exe", "google-chrome"),
    "firefox": ("firefox.exe", "firefox"),
    "edge": ("msedge.exe", "microsoft-edge"),
    "spotify": ("Spotify.exe", "spotify"),
    "discord": ("Discord.exe", "discord"),
    "vscode": ("Code.exe", "code"),
    "vs code": ("Code.exe", "code"),
}

# Pre-compiled regex patterns for command matching
_RE_OPEN = re.compile(r"^(?:open|launch|start|run)\s+(.+)", re.IGNORECASE)
_RE_GOTO = re.compile(r"^(?:go to|navigate to|visit)\s+(.+)", re.IGNORECASE)
_RE_SEARCH = re.compile(r"^(?:search|search for|google|look up)\s+(.+)", re.IGNORECASE)
_RE_CLOSE = re.compile(r"^(?:close|kill|stop|end)\s+(.+)", re.IGNORECASE)
_RE_TIME = re.compile(r"what(?:'s| is) the time|what time is it|tell me the time", re.IGNORECASE)
_RE_DATE = re.compile(r"what(?:'s| is) the date|what(?:'s| is) today|tell me the date", re.IGNORECASE)
_RE_EYES = re.compile(
    r"what do you see|what(?:'s| is) on (?:my |the )?screen|"
    r"look at (?:my |the )?screen|describe (?:my |the )?screen|"
    r"what are you looking at|take a screenshot|"
    r"what(?:'s| is) on (?:my |the )?(?:display|monitor)|"
    r"can you see (?:my |the )?screen|read (?:my |the )?screen",
    re.IGNORECASE,
)
_RE_COMPUTER = re.compile(
    r"click (?:on |the )?|log ?in(?:to| to)?|sign ?in(?:to| to)?|"
    r"type .+ (?:in|into|on)|go to .+ and (?:click|type|enter)|"
    r"fill .+ out|navigate to .+ and (?:click|type)|"
    r"scroll (?:up|down)|press (?:enter|tab|escape)",
    re.IGNORECASE,
)
_RE_URL = [
    re.compile(r"^https?://", re.IGNORECASE),
    re.compile(r"^www\.", re.IGNORECASE),
    re.compile(r"\.(com|org|net|io|dev|co|edu|gov|app|me|tv|gg)(/|$)", re.IGNORECASE),
]


class Actions:
    """Parses user commands and executes system actions."""

    def __init__(self):
        self.is_windows = sys.platform == "win32"

    def try_handle(self, text: str) -> tuple[bool, str | None]:
        """Try to parse and execute an action from the user's text.

        Returns:
            (handled, response) — if handled is True, response is what to say.
            If handled is False, the text should go to the LLM instead.
        """
        lower = text.lower().strip()

        # --- "open [something]" ---
        match = _RE_OPEN.match(lower)
        if match:
            target = match.group(1).strip()
            return self._handle_open(target, text)

        # --- "go to [url]" ---
        match = _RE_GOTO.match(lower)
        if match:
            target = match.group(1).strip()
            return self._handle_url(target)

        # --- "search for [query]" / "google [query]" ---
        match = _RE_SEARCH.match(lower)
        if match:
            query = match.group(1).strip()
            return self._handle_search(query)

        # --- "close [app]" ---
        match = _RE_CLOSE.match(lower)
        if match:
            target = match.group(1).strip()
            return self._handle_close(target)

        # --- "what time is it" ---
        if _RE_TIME.search(lower):
            now = datetime.now().strftime("%I:%M %p")
            return True, f"It's {now}."

        # --- "what's the date" ---
        if _RE_DATE.search(lower):
            today = datetime.now().strftime("%A, %B %d, %Y")
            return True, f"Today is {today}."

        # --- "what do you see" / "look at my screen" ---
        if _RE_EYES.search(lower):
            return True, "__EYES__"

        # --- computer control commands ---
        if _RE_COMPUTER.search(lower):
            return True, "__COMPUTER__"

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
        for name, cmd in APPS.items():
            if target == name or target == f"the {name}":
                return self._open_app(cmd, name)

        # Try partial matching (e.g., "open the chrome browser" matches "chrome")
        for name, cmd in APPS.items():
            if name in target:
                return self._open_app(cmd, name)

        for name, url in WEBSITE_SHORTCUTS.items():
            if name in target:
                return self._open_url(url, name)

        # Unknown target — try opening it directly (might be a file path)
        return self._open_unknown(target)

    def _handle_url(self, target: str) -> tuple[bool, str]:
        """Handle URL navigation."""
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
        """Handle 'close [app]' commands (cross-platform)."""
        # Find matching process name
        proc_win = None
        proc_linux = None
        for name, (win_proc, linux_proc) in PROCESS_NAMES.items():
            if name in target:
                proc_win = win_proc
                proc_linux = linux_proc
                break

        if proc_win is None:
            return True, f"I don't know how to close {target}."

        try:
            if self.is_windows:
                subprocess.run(
                    ["taskkill", "/IM", proc_win, "/F"],
                    capture_output=True, timeout=5,
                )
            else:
                subprocess.run(
                    ["killall", proc_linux],
                    capture_output=True, timeout=5,
                )
            logger.info("Closed %s", target)
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
        return any(pattern.search(text) for pattern in _RE_URL)
