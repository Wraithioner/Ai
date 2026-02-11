"""Persistent notes/memory module — survives restarts via filesystem."""

import json
import os
from pathlib import Path
from datetime import datetime

NOTES_DIR = Path(os.environ.get("NOTES_DIR", "/app/data/notes"))


def _ensure_dir():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)


def _notes_file() -> Path:
    return NOTES_DIR / "notes.json"


def _load() -> list[dict]:
    _ensure_dir()
    path = _notes_file()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save(notes: list[dict]):
    _ensure_dir()
    _notes_file().write_text(json.dumps(notes, indent=2))


def add_note(content: str) -> str:
    """Save a note."""
    notes = _load()
    note = {
        "id": len(notes) + 1,
        "content": content,
        "created": datetime.now().isoformat(),
    }
    notes.append(note)
    _save(notes)
    return f"Note #{note['id']} saved."


def list_notes() -> str:
    """List all notes."""
    notes = _load()
    if not notes:
        return "No notes yet. Use `/note <text>` to save one."
    lines = []
    for n in notes:
        lines.append(f"**#{n['id']}** — {n['content']}\n_{n['created']}_")
    return "\n\n".join(lines)


def get_note(note_id: str) -> str:
    """Get a specific note by ID."""
    try:
        nid = int(note_id)
    except ValueError:
        return "Invalid note ID."
    notes = _load()
    for n in notes:
        if n["id"] == nid:
            return f"**#{n['id']}**\n{n['content']}\n\nCreated: {n['created']}"
    return f"Note #{nid} not found."


def delete_note(note_id: str) -> str:
    """Delete a note by ID."""
    try:
        nid = int(note_id)
    except ValueError:
        return "Invalid note ID."
    notes = _load()
    original_len = len(notes)
    notes = [n for n in notes if n["id"] != nid]
    if len(notes) == original_len:
        return f"Note #{nid} not found."
    _save(notes)
    return f"Note #{nid} deleted."


def clear_notes() -> str:
    """Delete all notes."""
    _save([])
    return "All notes cleared."
