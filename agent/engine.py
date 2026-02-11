"""Core agent engine — parses messages and routes to the right module."""

import shlex
from agent.modules import system, files, web, process, notes, download, scheduler
from agent.utils.config import AI_PROVIDER

HELP_TEXT = """**Your Personal Agent** — here's everything I can do:

**System**
/run `<command>` — Execute a shell command
/sysinfo — Show system information
/ps `[filter]` — List running processes
/kill `<pid>` — Kill a process
/uptime — Bot uptime

**Files**
/ls `[path]` — List directory contents
/read `<path>` — Read a file
/head `<path>` `[lines]` — Read first N lines
/write `<path>` `<content>` — Write to a file
/delete `<path>` — Delete a file

**Web**
/fetch `<url>` — Fetch a webpage
/download `<url>` `[filename]` — Download a file
/downloads — List downloaded files

**Notes (persistent memory)**
/note `<text>` — Save a note
/notes — List all notes
/getnote `<id>` — View a note
/delnote `<id>` — Delete a note
/clearnotes — Clear all notes

**Reminders**
/remind `<minutes>` `<message>` — Set a reminder
/reminders — List pending reminders
/cancelremind `<id>` — Cancel a reminder

**General**
/help — Show this message
/ping — Check if I'm alive
/id — Show your Telegram user ID"""


async def handle_message(text: str) -> str:
    """Process an incoming message and return a response."""
    text = text.strip()
    if not text:
        return "Send me a message or type /help to see what I can do."

    if text.startswith("/"):
        return await _handle_command(text)

    if AI_PROVIDER != "none":
        return await _ai_respond(text)

    return (
        f'You said: "{text}"\n\n'
        "I hear you, but I need an AI brain to have real conversations.\n"
        "Once you connect an AI API, I'll chat properly.\n\n"
        "Type /help to see what I can do right now."
    )


async def _handle_command(text: str) -> str:
    """Route slash commands to the right module."""
    # Strip bot mention from group chats (e.g., /help@mybotname)
    parts = text.split(None, 1)
    cmd = parts[0].lower().split("@")[0]
    args = parts[1] if len(parts) > 1 else ""

    match cmd:
        # --- General ---
        case "/start" | "/help":
            return HELP_TEXT
        case "/ping":
            return "Pong! I'm alive and running."
        case "/id":
            return "Use this command in the bot chat — your ID is shown by the bot."

        # --- System ---
        case "/run":
            if not args:
                return "Usage: `/run <command>`\nExample: `/run ls -la`"
            return await system.run_command(args)
        case "/sysinfo":
            return system.system_info()
        case "/ps":
            return await process.list_processes(args)
        case "/kill":
            if not args:
                return "Usage: `/kill <pid>`"
            return await process.kill_process(args.strip())
        case "/uptime":
            return process.uptime()

        # --- Files ---
        case "/ls":
            return files.list_dir(args or ".")
        case "/read":
            if not args:
                return "Usage: `/read <path>`"
            return files.read_file(args.strip())
        case "/head":
            try:
                p = shlex.split(args)
            except ValueError:
                p = args.split()
            if not p:
                return "Usage: `/head <path> [lines]`"
            path = p[0]
            lines = int(p[1]) if len(p) > 1 else 20
            return files.head_file(path, lines)
        case "/write":
            if not args:
                return "Usage: `/write <path> <content>`"
            split = args.split(None, 1)
            if len(split) < 2:
                return "Usage: `/write <path> <content>`"
            return files.write_file(split[0], split[1])
        case "/delete":
            if not args:
                return "Usage: `/delete <path>`"
            return files.delete_file(args.strip())

        # --- Web ---
        case "/fetch":
            if not args:
                return "Usage: `/fetch <url>`"
            return web.fetch_url(args.strip())
        case "/download":
            if not args:
                return "Usage: `/download <url> [filename]`"
            p = args.split(None, 1)
            url = p[0]
            fname = p[1] if len(p) > 1 else ""
            return download.download_file(url, fname)
        case "/downloads":
            return download.list_downloads()

        # --- Notes ---
        case "/note":
            if not args:
                return "Usage: `/note <text>`"
            return notes.add_note(args)
        case "/notes":
            return notes.list_notes()
        case "/getnote":
            if not args:
                return "Usage: `/getnote <id>`"
            return notes.get_note(args.strip())
        case "/delnote":
            if not args:
                return "Usage: `/delnote <id>`"
            return notes.delete_note(args.strip())
        case "/clearnotes":
            return notes.clear_notes()

        # --- Reminders ---
        case "/remind":
            if not args:
                return "Usage: `/remind <minutes> <message>`\nExample: `/remind 30 Check the deployment`"
            p = args.split(None, 1)
            if len(p) < 2:
                return "Usage: `/remind <minutes> <message>`"
            try:
                minutes = int(p[0])
            except ValueError:
                return "First argument must be a number of minutes."
            return scheduler.set_reminder(minutes, p[1])
        case "/reminders":
            return scheduler.list_reminders()
        case "/cancelremind":
            if not args:
                return "Usage: `/cancelremind <id>`"
            return scheduler.cancel_reminder(args.strip())

        case _:
            return f"Unknown command: `{cmd}`\nType /help to see available commands."


async def _ai_respond(text: str) -> str:
    """Placeholder for AI API integration."""
    return "AI integration not yet configured. Set AI_PROVIDER and AI_API_KEY in Railway variables."
