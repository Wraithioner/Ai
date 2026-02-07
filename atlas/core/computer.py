"""Computer control module - gives Atlas hands to use the mouse and keyboard."""

import logging

logger = logging.getLogger(__name__)


class Computer:
    """Controls the mouse and keyboard using pyautogui.

    Safety features:
    - Disabled by default (must be enabled in config)
    - pyautogui.FAILSAFE = True (move mouse to top-left corner to abort)
    - Configurable pause between actions
    - All actions are logged
    """

    def __init__(self, config: dict):
        comp_cfg = config.get("computer", {})
        self.enabled = comp_cfg.get("enabled", False)
        self._failsafe = comp_cfg.get("failsafe", True)
        self._pause = comp_cfg.get("pause", 0.5)
        self._initialized = False

    def _ensure_ready(self):
        """Lazy-initialize pyautogui with safety settings."""
        if not self.enabled:
            raise RuntimeError(
                "Computer control is disabled. Set computer.enabled: true in config/settings.yaml"
            )

        if not self._initialized:
            import pyautogui
            pyautogui.FAILSAFE = self._failsafe
            pyautogui.PAUSE = self._pause
            self._initialized = True

    def click(self, x: int, y: int):
        """Move to (x, y) and left-click."""
        import pyautogui
        self._ensure_ready()
        logger.info("Click at (%d, %d)", x, y)
        pyautogui.click(x, y)

    def double_click(self, x: int, y: int):
        """Move to (x, y) and double-click."""
        import pyautogui
        self._ensure_ready()
        logger.info("Double-click at (%d, %d)", x, y)
        pyautogui.doubleClick(x, y)

    def right_click(self, x: int, y: int):
        """Move to (x, y) and right-click."""
        import pyautogui
        self._ensure_ready()
        logger.info("Right-click at (%d, %d)", x, y)
        pyautogui.rightClick(x, y)

    def type_text(self, text: str, interval: float = 0.05):
        """Type text character by character."""
        import pyautogui
        self._ensure_ready()
        logger.info("Typing: %s", text[:50])
        pyautogui.write(text, interval=interval)

    def press_key(self, key: str):
        """Press a single key (enter, tab, escape, space, backspace, etc.)."""
        import pyautogui
        self._ensure_ready()
        logger.info("Press key: %s", key)
        pyautogui.press(key)

    def hotkey(self, *keys: str):
        """Press a key combination (e.g., hotkey('ctrl', 'c'))."""
        import pyautogui
        self._ensure_ready()
        logger.info("Hotkey: %s", "+".join(keys))
        pyautogui.hotkey(*keys)

    def scroll(self, clicks: int, x: int | None = None, y: int | None = None):
        """Scroll up (positive) or down (negative)."""
        import pyautogui
        self._ensure_ready()
        logger.info("Scroll %d at (%s, %s)", clicks, x, y)
        pyautogui.scroll(clicks, x=x, y=y)

    def move_to(self, x: int, y: int):
        """Move the mouse cursor to (x, y) without clicking."""
        import pyautogui
        self._ensure_ready()
        logger.info("Move to (%d, %d)", x, y)
        pyautogui.moveTo(x, y)
