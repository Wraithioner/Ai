/** Command router — maps commands to skills. */

import * as system from "./skills/system.js";
import * as files from "./skills/files.js";
import * as net from "./skills/net.js";
import * as git from "./skills/git.js";
import * as notes from "./skills/notes.js";
import * as scheduler from "./skills/scheduler.js";
import * as comms from "./skills/comms.js";
import { runPython } from "./utils/python.js";
import { persona } from "./personality.js";
import { evalJS } from "./skills/eval.js";
import * as status from "./skills/status.js";
import * as history from "./skills/history.js";

const HELP = `**Your Personal Agent** — here's everything I can do:

**System**
/run \`<cmd>\` — Execute a shell command
/sysinfo — System information
/ps \`[filter]\` — List processes
/kill \`<pid>\` — Kill a process
/uptime — Bot uptime
/env \`[name]\` — Show environment variables

**Files**
/ls \`[path]\` — List directory
/read \`<path>\` — Read a file
/head \`<path>\` \`[lines]\` — First N lines
/write \`<path>\` \`<content>\` — Write to file
/rm \`<path>\` — Delete a file
/find \`<dir>\` \`<pattern>\` — Search files by name

**Network**
/fetch \`<url>\` — Fetch a webpage
/download \`<url>\` \`[name]\` — Download a file
/downloads — List downloads
/ping \`<host>\` — Ping a host
/dns \`<domain>\` — DNS lookup
/headers \`<url>\` — HTTP headers

**Git**
/git status — Repo status
/git log \`[n]\` — Recent commits
/git diff — Changed files
/git clone \`<url>\` — Clone a repo
/git pull — Pull latest
/git branch — List branches

**Notes**
/note \`<text>\` — Save a note
/notes — List notes
/getnote \`<id>\` — View note
/delnote \`<id>\` — Delete note
/clearnotes — Clear all

**Reminders**
/remind \`<min>\` \`<msg>\` — Set reminder
/reminders — List pending
/cancel \`<id>\` — Cancel reminder

**Communication**
/email \`<to>\` \`<subject>\` \`<body>\` — Send email
/webhook \`<url>\` \`<msg>\` — Send webhook
/discord \`<webhook_url>\` \`<msg>\` — Send to Discord
/slack \`<webhook_url>\` \`<msg>\` — Send to Slack
/api \`<METHOD>\` \`<url>\` \`[body]\` — HTTP API call

**Code**
/eval \`<js>\` — Run JavaScript (sandboxed, instant)
/py \`<code>\` — Run Python code
/scrape \`<url>\` — Scrape a webpage

**General**
/help — This message
/status — Dashboard overview
/history \`[n]\` — Command history
/clearhistory — Clear history
/ping — Am I alive?
/id — Your Telegram ID`;

export { HELP };

export async function route(text: string, user = "unknown"): Promise<string> {
  const parts = text.split(/\s+/);
  const cmd = parts[0].toLowerCase().split("@")[0]; // strip @botname
  const args = text.slice(parts[0].length).trim();

  // Track command
  history.record(text, user);
  status.trackCommand(cmd);

  switch (cmd) {
    // --- General ---
    case "/start":
    case "/help":
      return HELP;
    case "/id":
      return "__ID__"; // handled specially in bot.ts

    // --- System ---
    case "/run":
      return args ? system.runCommand(args) : "Usage: `/run <command>`";
    case "/sysinfo":
      return system.sysInfo();
    case "/ps":
      return system.listProcesses(args || undefined);
    case "/kill":
      return args ? system.killProcess(args.trim()) : "Usage: `/kill <pid>`";
    case "/uptime":
      return system.botUptime();
    case "/env":
      if (!args) return "Usage: `/env <name>` or `/env` to list all";
      return process.env[args.trim()] ?? `${args.trim()} not set`;

    // --- Files ---
    case "/ls":
      return files.listDir(args || ".");
    case "/read":
      return args ? files.readFile(args.trim()) : "Usage: `/read <path>`";
    case "/head": {
      const p = args.split(/\s+/);
      if (!p[0]) return "Usage: `/head <path> [lines]`";
      return files.headFile(p[0], parseInt(p[1]) || 20);
    }
    case "/write": {
      const idx = args.indexOf(" ");
      if (idx === -1) return "Usage: `/write <path> <content>`";
      return files.writeFile(args.slice(0, idx), args.slice(idx + 1));
    }
    case "/rm":
      return args ? files.deleteFile(args.trim()) : "Usage: `/rm <path>`";
    case "/find": {
      const p = args.split(/\s+/, 2);
      if (p.length < 2) return "Usage: `/find <dir> <pattern>`";
      return files.searchFiles(p[0], p[1]);
    }

    // --- Network ---
    case "/fetch":
      return args ? net.fetchUrl(args.trim()) : "Usage: `/fetch <url>`";
    case "/download": {
      const p = args.split(/\s+/, 2);
      if (!p[0]) return "Usage: `/download <url> [filename]`";
      return net.downloadFile(p[0], p[1]);
    }
    case "/downloads":
      return net.listDownloads();
    case "/ping":
      if (!args) return persona.responses.ping;
      return net.ping(args.trim());
    case "/dns":
      return args ? net.dnsLookup(args.trim()) : "Usage: `/dns <domain>`";
    case "/headers":
      return args ? net.curl(args.trim()) : "Usage: `/headers <url>`";

    // --- Git ---
    case "/git": {
      const sub = args.split(/\s+/);
      const subcmd = sub[0]?.toLowerCase();
      const subargs = args.slice((sub[0]?.length ?? 0)).trim();
      switch (subcmd) {
        case "status": return git.gitStatus();
        case "log": return git.gitLog(parseInt(subargs) || 10);
        case "diff": return git.gitDiff();
        case "clone": return subargs ? git.gitClone(subargs) : "Usage: `/git clone <url>`";
        case "pull": return git.gitPull();
        case "branch": return git.gitBranch();
        default: return "Git subcommands: status, log, diff, clone, pull, branch";
      }
    }

    // --- Notes ---
    case "/note":
      return args ? notes.addNote(args) : "Usage: `/note <text>`";
    case "/notes":
      return notes.listNotes();
    case "/getnote":
      return args ? notes.getNote(args.trim()) : "Usage: `/getnote <id>`";
    case "/delnote":
      return args ? notes.deleteNote(args.trim()) : "Usage: `/delnote <id>`";
    case "/clearnotes":
      return notes.clearNotes();

    // --- Reminders ---
    case "/remind": {
      const p = args.split(/\s+/, 2);
      const mins = parseInt(p[0]);
      const msg = args.slice(p[0]?.length ?? 0).trim();
      if (isNaN(mins) || !msg) return "Usage: `/remind <minutes> <message>`";
      return scheduler.setReminder(mins, msg);
    }
    case "/reminders":
      return scheduler.listReminders();
    case "/cancel":
      return args ? scheduler.cancelReminder(args.trim()) : "Usage: `/cancel <id>`";

    // --- Communication ---
    case "/email": {
      const p = args.split(/\s+/, 3);
      if (p.length < 3) return "Usage: `/email <to> <subject> <body>`\nSubject with spaces: use quotes";
      const to = p[0];
      const rest = args.slice(to.length).trim();
      const subjEnd = rest.indexOf(" ");
      if (subjEnd === -1) return "Usage: `/email <to> <subject> <body>`";
      return comms.sendEmail(to, rest.slice(0, subjEnd), rest.slice(subjEnd + 1));
    }
    case "/webhook": {
      const idx = args.indexOf(" ");
      if (idx === -1) return "Usage: `/webhook <url> <message>`";
      return comms.sendWebhook(args.slice(0, idx), args.slice(idx + 1));
    }
    case "/discord": {
      const idx = args.indexOf(" ");
      if (idx === -1) return "Usage: `/discord <webhook_url> <message>`";
      return comms.sendDiscord(args.slice(0, idx), args.slice(idx + 1));
    }
    case "/slack": {
      const idx = args.indexOf(" ");
      if (idx === -1) return "Usage: `/slack <webhook_url> <message>`";
      return comms.sendSlack(args.slice(0, idx), args.slice(idx + 1));
    }
    case "/api": {
      const p = args.split(/\s+/, 3);
      if (p.length < 2) return "Usage: `/api <GET|POST|PUT|DELETE> <url> [json_body]`";
      return comms.apiCall(p[0], p[1], p[2]);
    }

    // --- Code ---
    case "/eval":
      return args ? evalJS(args) : "Usage: `/eval <javascript>`";
    case "/py":
      return args ? runPython("run_code.py", [args]) : "Usage: `/py <code>`";
    case "/scrape":
      return args ? runPython("scrape.py", [args.trim()]) : "Usage: `/scrape <url>`";

    // --- Meta ---
    case "/status":
      return status.getStatus();
    case "/history": {
      const count = parseInt(args) || 20;
      return history.getHistory(count);
    }
    case "/clearhistory":
      return history.clearHistory();

    default:
      return persona.responses.unknownCommand(cmd);
  }
}
