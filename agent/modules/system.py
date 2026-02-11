"""System command execution module."""

import asyncio
import os
import platform
import shutil


async def run_command(command: str, timeout: int = 30) -> str:
    """Execute a shell command and return its output."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode().strip()
        errors = stderr.decode().strip()

        result = ""
        if output:
            result += output
        if errors:
            result += f"\n[stderr] {errors}" if result else f"[stderr] {errors}"
        if not result:
            result = f"Command finished with exit code {proc.returncode}"
        return result

    except asyncio.TimeoutError:
        proc.kill()
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def system_info() -> str:
    """Return basic system information."""
    info = [
        f"OS: {platform.system()} {platform.release()}",
        f"Architecture: {platform.machine()}",
        f"Python: {platform.python_version()}",
        f"Hostname: {platform.node()}",
        f"User: {os.getenv('USER', 'unknown')}",
        f"Working dir: {os.getcwd()}",
    ]

    disk = shutil.disk_usage("/")
    info.append(f"Disk: {disk.free // (1024**3)}GB free / {disk.total // (1024**3)}GB total")

    return "\n".join(info)
