"""Core agent engine — parses messages and routes to the right module."""

import shlex
from agent.modules import system, files, web
from agent.utils.config import AI_PROVIDER

HELP_TEXT = """I'm your personal agent. Here's what I can do:

**System**
`/run <command>` — Execute a shell command
`/sysinfo` — Show system information

**Files**
`/ls [path]` — List directory contents
`/read <path>` — Read a file
`/head <path> [lines]` — Read first N lines
`/write <path> <content>` — Write to a file
`/delete <path>` — Delete a file

**Web**
`/fetch <url>` — Fetch a webpage

**General**
`/help` — Show this help
`/ping` — Check if I'm alive

Send me any message and I'll respond. Once an AI API is connected, I'll be able to have real conversations."""


async def handle_message(text: str) -> str:
    """Process an incoming message and return a response."""
    text = text.strip()
    if not text:
        return "Send me a message or type /help to see what I can do."

    # Command routing
    if text.startswith("/"):
        return await _handle_command(text)

    # Free-form text — placeholder for AI integration
    if AI_PROVIDER != "none":
        return await _ai_respond(text)

    return (
        f'You said: "{text}"\n\n'
        "I can echo for now. Once you connect an AI API, "
        "I'll have real conversations with you.\n\n"
        "Type /help to see what I can do right now."
    )


async def _handle_command(text: str) -> str:
    """Route slash commands to the right module."""
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    match cmd:
        case "/help" | "/start":
            return HELP_TEXT

        case "/ping":
            return "Pong! I'm alive."

        case "/run":
            if not args:
                return "Usage: `/run <command>`"
            return await system.run_command(args)

        case "/sysinfo":
            return system.system_info()

        case "/ls":
            return files.list_dir(args or ".")

        case "/read":
            if not args:
                return "Usage: `/read <path>`"
            return files.read_file(args)

        case "/head":
            try:
                parts = shlex.split(args)
            except ValueError:
                parts = args.split()
            if not parts:
                return "Usage: `/head <path> [lines]`"
            path = parts[0]
            lines = int(parts[1]) if len(parts) > 1 else 20
            return files.head_file(path, lines)

        case "/write":
            try:
                parts = shlex.split(args)
            except ValueError:
                parts = args.split(None, 1)
            if len(parts) < 2:
                return "Usage: `/write <path> <content>`"
            return files.write_file(parts[0], parts[1])

        case "/delete":
            if not args:
                return "Usage: `/delete <path>`"
            return files.delete_file(args)

        case "/fetch":
            if not args:
                return "Usage: `/fetch <url>`"
            return web.fetch_url(args)

        case _:
            return f"Unknown command: `{cmd}`\nType /help to see available commands."


async def _ai_respond(text: str) -> str:
    """Placeholder for AI API integration."""
    return "AI integration not yet configured. Set AI_PROVIDER and AI_API_KEY in Railway."
