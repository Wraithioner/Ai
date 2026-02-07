"""Safety module - prevents Atlas from doing dangerous things."""

import logging
import time

logger = logging.getLogger(__name__)

# Buttons that could cause irreversible damage
DANGEROUS_BUTTONS = [
    "buy", "sell", "trade", "place order", "confirm purchase",
    "submit order", "checkout", "pay now", "send payment",
    "transfer", "withdraw", "deposit",
    "delete", "remove", "erase", "uninstall",
    "send", "post", "publish", "tweet", "reply all",
    "confirm", "agree", "accept",
    "format", "factory reset",
]

# Screen text that indicates a financial context
FINANCIAL_KEYWORDS = [
    "bank", "banking", "trading", "broker", "wallet",
    "payment", "checkout", "credit card", "debit card",
    "balance", "portfolio", "exchange", "crypto",
    "coinbase", "binance", "robinhood", "paypal",
    "venmo", "zelle", "stripe",
]

# Actions that should never be performed automatically
BLOCKED_ACTIONS = [
    "delete account", "format disk", "factory reset",
    "rm -rf", "drop table", "shutdown",
]


class Safety:
    """Checks proposed actions for safety before execution.

    Features:
    - Dangerous button detection (buy, sell, delete, send, etc.)
    - Financial site awareness (extra caution on banking/trading pages)
    - Blocked action list (things Atlas should never do)
    - Rate limiting (max actions per minute)
    - Step limiting (max steps per task)
    """

    def __init__(self, config: dict):
        safety_cfg = config.get("safety", {})
        self.enabled = safety_cfg.get("enabled", True)
        self.confirm_financial = safety_cfg.get("confirm_financial", True)
        self.max_steps = safety_cfg.get("max_steps_per_task", 10)
        self.max_actions_per_minute = safety_cfg.get("max_actions_per_minute", 20)
        self.blocked_keywords = safety_cfg.get("blocked_keywords", BLOCKED_ACTIONS)

        # Rate limiting state
        self._action_timestamps: list[float] = []

    def check_action(self, action: dict, screen_text: str) -> tuple[bool, str]:
        """Check if a proposed action is safe to execute.

        Args:
            action: dict from Brain.plan_action() with "action", "target", "value", "reason"
            screen_text: current OCR text from the screen

        Returns:
            (safe, reason) — if safe is False, reason explains why it was blocked
        """
        if not self.enabled:
            return True, ""

        action_type = action.get("action", "")
        target = action.get("target", "").lower()
        value = action.get("value", "").lower()

        # Check for blocked actions
        combined = f"{target} {value} {action.get('reason', '')}".lower()
        for blocked in self.blocked_keywords:
            if blocked.lower() in combined:
                msg = f"Blocked: action involves '{blocked}' which is not allowed."
                logger.warning(msg)
                return False, msg

        # Check rate limiting
        if not self._check_rate_limit():
            msg = f"Rate limit exceeded: more than {self.max_actions_per_minute} actions per minute."
            logger.warning(msg)
            return False, msg

        # Check if clicking a dangerous button
        if action_type == "click" and target:
            for dangerous in DANGEROUS_BUTTONS:
                if dangerous in target:
                    # In financial context, always block
                    if self.confirm_financial and self._is_financial_context(screen_text):
                        msg = (
                            f"Safety block: about to click '{target}' on a financial page. "
                            "This requires your explicit confirmation."
                        )
                        logger.warning(msg)
                        return False, msg
                    # Outside financial context, warn but allow
                    logger.info("Caution: clicking '%s' (potentially dangerous button).", target)

        # Check if typing sensitive data
        if action_type == "type" and value:
            if self._looks_like_sensitive_data(value):
                msg = "Blocked: refusing to type what looks like sensitive data (card number, SSN, etc.)."
                logger.warning(msg)
                return False, msg

        # Record this action for rate limiting
        self._action_timestamps.append(time.time())

        return True, ""

    def _is_financial_context(self, screen_text: str) -> bool:
        """Check if screen text suggests a financial site."""
        lower = screen_text.lower()
        for keyword in FINANCIAL_KEYWORDS:
            if keyword in lower:
                return True
        return False

    def _looks_like_sensitive_data(self, text: str) -> bool:
        """Check if text looks like a credit card number, SSN, etc."""
        import re

        stripped = text.replace(" ", "").replace("-", "")

        # Credit card pattern (13-19 digits)
        if re.match(r"^\d{13,19}$", stripped):
            return True

        # SSN pattern (9 digits or xxx-xx-xxxx)
        if re.match(r"^\d{9}$", stripped):
            return True
        if re.match(r"^\d{3}-\d{2}-\d{4}$", text.strip()):
            return True

        return False

    def _check_rate_limit(self) -> bool:
        """Check if we're within the allowed actions-per-minute rate."""
        now = time.time()
        one_minute_ago = now - 60

        # Clean old timestamps
        self._action_timestamps = [
            ts for ts in self._action_timestamps if ts > one_minute_ago
        ]

        return len(self._action_timestamps) < self.max_actions_per_minute
