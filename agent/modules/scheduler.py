"""Scheduler module — set reminders and recurring tasks."""

import json
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SCHEDULE_DIR = Path(os.environ.get("SCHEDULE_DIR", "/app/data/schedule"))
_reminder_callback = None
_running = False


def _ensure_dir():
    SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)


def _reminders_file() -> Path:
    return SCHEDULE_DIR / "reminders.json"


def _load() -> list[dict]:
    _ensure_dir()
    path = _reminders_file()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(reminders: list[dict]):
    _ensure_dir()
    _reminders_file().write_text(json.dumps(reminders, indent=2))


def set_reminder(minutes: int, message: str) -> str:
    """Set a reminder for N minutes from now."""
    if minutes < 1 or minutes > 10080:
        return "Reminder must be between 1 minute and 7 days (10080 minutes)."

    reminders = _load()
    trigger_at = datetime.now() + timedelta(minutes=minutes)
    reminder = {
        "id": len(reminders) + 1,
        "message": message,
        "trigger_at": trigger_at.isoformat(),
        "created": datetime.now().isoformat(),
        "fired": False,
    }
    reminders.append(reminder)
    _save(reminders)

    if minutes >= 60:
        time_str = f"{minutes // 60}h {minutes % 60}m" if minutes % 60 else f"{minutes // 60}h"
    else:
        time_str = f"{minutes}m"

    return f"Reminder #{reminder['id']} set for {time_str} from now.\n_{trigger_at.strftime('%H:%M %b %d')}_"


def list_reminders() -> str:
    """List pending reminders."""
    reminders = _load()
    pending = [r for r in reminders if not r.get("fired")]
    if not pending:
        return "No pending reminders."
    lines = []
    for r in pending:
        trigger = datetime.fromisoformat(r["trigger_at"])
        lines.append(f"**#{r['id']}** — {r['message']}\nFires at: _{trigger.strftime('%H:%M %b %d')}_")
    return "\n\n".join(lines)


def cancel_reminder(reminder_id: str) -> str:
    """Cancel a reminder by ID."""
    try:
        rid = int(reminder_id)
    except ValueError:
        return "Invalid reminder ID."
    reminders = _load()
    for r in reminders:
        if r["id"] == rid and not r.get("fired"):
            r["fired"] = True
            _save(reminders)
            return f"Reminder #{rid} cancelled."
    return f"Reminder #{rid} not found or already fired."


def register_callback(callback):
    """Register a callback function to be called when a reminder fires."""
    global _reminder_callback
    _reminder_callback = callback


async def start_scheduler():
    """Background loop that checks for due reminders."""
    global _running
    _running = True
    logger.info("Scheduler started")
    while _running:
        try:
            reminders = _load()
            now = datetime.now()
            changed = False
            for r in reminders:
                if r.get("fired"):
                    continue
                trigger = datetime.fromisoformat(r["trigger_at"])
                if now >= trigger:
                    r["fired"] = True
                    changed = True
                    if _reminder_callback:
                        try:
                            await _reminder_callback(r["message"])
                        except Exception as e:
                            logger.error(f"Reminder callback failed: {e}")
            if changed:
                _save(reminders)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        await asyncio.sleep(15)


def stop_scheduler():
    """Stop the scheduler loop."""
    global _running
    _running = False
