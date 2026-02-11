"""File management module."""

import os
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE", "/app"))


def read_file(path: str) -> str:
    """Read and return file contents."""
    try:
        target = _resolve(path)
        if not target.exists():
            return f"File not found: {path}"
        if target.stat().st_size > 50_000:
            return f"File too large ({target.stat().st_size} bytes). Use 'head <path> <lines>' instead."
        return target.read_text()
    except Exception as e:
        return f"Error: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        target = _resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Wrote {len(content)} bytes to {target}"
    except Exception as e:
        return f"Error: {e}"


def list_dir(path: str = ".") -> str:
    """List directory contents."""
    try:
        target = _resolve(path)
        if not target.is_dir():
            return f"Not a directory: {path}"
        entries = sorted(target.iterdir())
        if not entries:
            return "(empty directory)"
        lines = []
        for entry in entries:
            prefix = "d " if entry.is_dir() else "f "
            size = entry.stat().st_size if entry.is_file() else 0
            lines.append(f"{prefix}{entry.name:<40} {size:>8} bytes")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def delete_file(path: str) -> str:
    """Delete a file."""
    try:
        target = _resolve(path)
        if not target.exists():
            return f"Not found: {path}"
        if target.is_dir():
            return "Use 'rmdir' for directories"
        target.unlink()
        return f"Deleted: {target}"
    except Exception as e:
        return f"Error: {e}"


def head_file(path: str, lines: int = 20) -> str:
    """Read first N lines of a file."""
    try:
        target = _resolve(path)
        if not target.exists():
            return f"File not found: {path}"
        with open(target) as f:
            result = []
            for i, line in enumerate(f):
                if i >= lines:
                    result.append(f"... ({lines}/{sum(1 for _ in f) + lines} lines shown)")
                    break
                result.append(line.rstrip())
        return "\n".join(result)
    except Exception as e:
        return f"Error: {e}"


def _resolve(path: str) -> Path:
    """Resolve a path relative to workspace."""
    p = Path(path)
    if p.is_absolute():
        return p
    return WORKSPACE / p
