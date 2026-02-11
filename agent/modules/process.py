"""Process and system monitoring module."""

import asyncio
import os
import time

_start_time = time.time()


def uptime() -> str:
    """Return bot uptime."""
    elapsed = int(time.time() - _start_time)
    days, remainder = divmod(elapsed, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return f"Bot uptime: {' '.join(parts)}"


async def list_processes(filter_str: str = "") -> str:
    """List running processes, optionally filtered."""
    cmd = "ps aux --sort=-%mem | head -20"
    if filter_str:
        cmd = f"ps aux | grep -i '{filter_str}' | grep -v grep | head -20"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode().strip()
    return output if output else "No matching processes found."


async def kill_process(pid: str) -> str:
    """Kill a process by PID."""
    try:
        pid_int = int(pid)
        os.kill(pid_int, 9)
        return f"Killed process {pid_int}"
    except ValueError:
        return "Invalid PID. Usage: `/kill <pid>`"
    except ProcessLookupError:
        return f"Process {pid} not found."
    except PermissionError:
        return f"Permission denied to kill process {pid}."
