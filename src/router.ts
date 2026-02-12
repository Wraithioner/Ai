/** Command router — maps commands to skills. */

import * as system from "./skills/system.js";
import * as files from "./skills/files.js";
import * as net from "./skills/net.js";
import * as git from "./skills/git.js";
import * as notes from "./skills/notes.js";
import * as scheduler from "./skills/scheduler.js";
import * as comms from "./skills/comms.js";
import * as cronSkill from "./skills/cron.js";
import * as alias from "./skills/alias.js";
import * as grepSkill from "./skills/grep.js";
import { runPython } from "./utils/python.js";
import { persona } from "./personality.js";
import { evalJS } from "./skills/eval.js";
import * as status from "./skills/status.js";
import * as history from "./skills/history.js";
import { safeEnvValue, listSafeEnvVars, codeBlock } from "./utils/sanitize.js";
import { config } from "./utils/config.js";
import * as arena from "./skills/arena.js";

const HELP = `${persona.name} v0.2 — your personal agent. Here's everything:

SYSTEM
/run <cmd> — Shell command
/sysinfo — System info
/ps [filter] — Processes
/kill <pid> — Kill process
/uptime — Bot uptime
/env [name] — Environment vars (sensitive masked)

FILES
/ls [path] — List directory
/read <path> — Read file
/head <path> [n] — First N lines
/write <path> <content> — Write file
/rm <path> — Delete file
/find <dir> <pattern> — Find files
/grep <pattern> [dir] — Search file contents

NETWORK
/fetch <url> — Fetch webpage
/download <url> [name] — Download file
/downloads — List downloads
/ping <host> — Ping host
/dns <domain> — DNS lookup
/headers <url> — HTTP headers

GIT
/git status|log|diff|clone|pull|branch

NOTES
/note <text> — Save note
/notes — List all
/getnote <id> — View
/delnote <id> — Delete
/clearnotes — Clear all

REMINDERS AND CRON
/remind <min> <msg> — One-time reminder
/reminders — List pending
/cancel <id> — Cancel reminder
/cron <min> <cmd> — Recurring task
/crons — List cron jobs
/rmcron <id> — Remove cron

COMMUNICATION
/email <to> <subject> <body> — Send email
/webhook <url> <msg> — Webhook
/discord <url> <msg> — Discord
/slack <url> <msg> — Slack
/api <METHOD> <url> [body] — API call

CODE
/eval <js> — JavaScript (sandboxed)
/py <code> — Python
/scrape <url> — Scrape page

TOOLS
/alias <name> <cmd> — Create shortcut
/aliases — List aliases
/rmalias <name> — Remove alias
/sendfile <path> — Send file to chat

ARENA
/arena post <text> — Post to Arena
/arena reply <id> <text> — Reply to post
/arena quote <id> <text> — Quote post
/arena like <id> — Like a post
/arena unlike <id> — Unlike a post
/arena repost <id> — Repost
/arena search <query> — Search users
/arena user <handle> — View profile
/arena trending — Trending users
/arena follow <handle> — Follow user
/arena unfollow <handle> — Unfollow user
/arena followers <handle> — List followers
/arena dm <convId> <msg> — Send DM
/arena convos — List conversations
/arena react <msgId> <emoji> — React to message
/arena stage <title> — Create audio room
/arena live <title> — Create livestream
/arena stages — Active stages
/arena lives — Active livestreams
/arena shares [handle] — Share stats
/arena holdings — Your holdings
/arena earnings — Earnings breakdown
/arena communities — Top communities
/arena csearch <query> — Search communities
/arena join <id> — Join community
/arena notifs — Notifications
/arena unseen — Unseen notifications
/arena seen — Mark all as seen
/arena profile — Your profile
/arena update <name|bio> <value> — Update profile
/arena register <name> <handle> <bio> — Register agent
/arena config — Show Arena env config status

META
/status — Dashboard
/history [n] — Command log
/clearhistory — Clear log
/help — This message
/id — Your Telegram ID`;

export { HELP };

export async function route(text: string, user = "unknown"): Promise<string> {
  const parts = text.split(/\s+/);
  let cmd = (parts[0] ?? "").toLowerCase().split("@")[0]!;
  const args = text.slice((parts[0] ?? "").length).trim();

  // Check for alias
  const aliasCmd = alias.resolveAlias(cmd.slice(1));
  if (aliasCmd) {
    const fullCmd = args ? `${aliasCmd} ${args}` : aliasCmd;
    return route(fullCmd, user);
  }

  // Track
  history.record(text, user);
  status.trackCommand(cmd);

  switch (cmd) {
    // --- General ---
    case "/start":
    case "/help":
      return HELP;
    case "/id":
      return "__ID__";

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
      if (!args) return codeBlock(listSafeEnvVars());
      return safeEnvValue(args.trim());

    // --- Files ---
    case "/ls":
      return files.listDir(args || ".");
    case "/read":
      return args ? files.readFile(args.trim()) : "Usage: `/read <path>`";
    case "/head": {
      const p = args.split(/\s+/);
      if (!p[0]) return "Usage: `/head <path> [lines]`";
      return files.headFile(p[0], parseInt(p[1] ?? "") || 20);
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
      if (!p[0] || !p[1]) return "Usage: `/find <dir> <pattern>`";
      return files.searchFiles(p[0], p[1]);
    }
    case "/grep": {
      const p = args.split(/\s+/, 2);
      if (!p[0]) return "Usage: `/grep <pattern> [dir]`";
      return grepSkill.grep(p[0], p[1] || ".");
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
        default: return "Git: status, log, diff, clone, pull, branch";
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
      const mins = parseInt(p[0] ?? "");
      const msg = args.slice((p[0] ?? "").length).trim();
      if (isNaN(mins) || !msg) return "Usage: `/remind <minutes> <message>`";
      return scheduler.setReminder(mins, msg);
    }
    case "/reminders":
      return scheduler.listReminders();
    case "/cancel":
      return args ? scheduler.cancelReminder(args.trim()) : "Usage: `/cancel <id>`";

    // --- Cron ---
    case "/cron": {
      const p = args.split(/\s+/, 2);
      const mins = parseInt(p[0] ?? "");
      const cronCmd = p[1];
      if (isNaN(mins) || !cronCmd) return "Usage: `/cron <interval_min> <command>`";
      return cronSkill.addCron(mins, cronCmd);
    }
    case "/crons":
      return cronSkill.listCrons();
    case "/rmcron":
      return args ? cronSkill.removeCron(args.trim()) : "Usage: `/rmcron <id>`";

    // --- Communication ---
    case "/email": {
      const p = args.split(/\s+/, 3);
      if (!p[0] || !p[1] || !p[2]) return "Usage: `/email <to> <subject> <body>`";
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
      if (!p[0] || !p[1]) return "Usage: `/api <GET|POST|PUT|DELETE> <url> [body]`";
      return comms.apiCall(p[0], p[1], p[2]);
    }

    // --- Code ---
    case "/eval":
      return args ? evalJS(args) : "Usage: `/eval <javascript>`";
    case "/py":
      return args ? runPython("run_code.py", [args]) : "Usage: `/py <code>`";
    case "/scrape":
      return args ? runPython("scrape.py", [args.trim()]) : "Usage: `/scrape <url>`";

    // --- Aliases ---
    case "/alias": {
      const p = args.split(/\s+/, 2);
      if (!p[0] || !p[1]) return "Usage: `/alias <name> <command>`";
      return alias.setAlias(p[0], p[1]);
    }
    case "/aliases":
      return alias.listAliases();
    case "/rmalias":
      return args ? alias.removeAlias(args.trim()) : "Usage: `/rmalias <name>`";

    // --- Arena ---
    case "/arena": {
      const sub = args.split(/\s+/);
      const subcmd = sub[0]?.toLowerCase();
      const subargs = args.slice((sub[0]?.length ?? 0)).trim();
      switch (subcmd) {
        case "post":
          return subargs ? arena.createPost(subargs) : "Usage: /arena post <text>";
        case "reply": {
          const sp = subargs.split(/\s+/, 2);
          if (!sp[0] || !sp[1]) return "Usage: /arena reply <postId> <text>";
          return arena.replyToPost(sp[0], subargs.slice(sp[0].length).trim());
        }
        case "quote": {
          const sp = subargs.split(/\s+/, 2);
          if (!sp[0] || !sp[1]) return "Usage: /arena quote <postId> <text>";
          return arena.quotePost(sp[0], subargs.slice(sp[0].length).trim());
        }
        case "like":
          return subargs ? arena.likePost(subargs) : "Usage: /arena like <postId>";
        case "unlike":
          return subargs ? arena.unlikePost(subargs) : "Usage: /arena unlike <postId>";
        case "repost":
          return subargs ? arena.repost(subargs) : "Usage: /arena repost <postId>";
        case "search":
          return subargs ? arena.searchUser(subargs) : "Usage: /arena search <query>";
        case "user":
          return arena.getUserByHandle(subargs || config.arenaHandle);
        case "trending":
          return arena.trending(parseInt(subargs) || 1);
        case "follow":
          return subargs ? arena.follow(subargs) : "Usage: /arena follow <handle>";
        case "unfollow":
          return subargs ? arena.unfollow(subargs) : "Usage: /arena unfollow <handle>";
        case "followers":
          return arena.getFollowers(subargs || config.arenaHandle);
        case "dm": {
          const sp = subargs.split(/\s+/, 2);
          if (!sp[0] || !sp[1]) return "Usage: /arena dm <conversationId> <message>";
          return arena.sendMessage(sp[0], subargs.slice(sp[0].length).trim());
        }
        case "convos":
          return arena.getConversations();
        case "react": {
          const sp = subargs.split(/\s+/, 2);
          if (!sp[0] || !sp[1]) return "Usage: /arena react <messageId> <emoji>";
          return arena.reactToMessage(sp[0], sp[1]);
        }
        case "stage":
          return subargs ? arena.createStage(subargs) : "Usage: /arena stage <title>";
        case "live":
          return subargs ? arena.createLivestream(subargs) : "Usage: /arena live <title>";
        case "stages":
          return arena.getStages();
        case "lives":
          return arena.getLivestreams();
        case "shares":
          return arena.shareStats(subargs || config.arenaHandle || undefined);
        case "holdings":
          return arena.holdings();
        case "earnings":
          return arena.earnings();
        case "communities":
          return arena.topCommunities();
        case "csearch":
          return subargs ? arena.searchCommunity(subargs) : "Usage: /arena csearch <query>";
        case "join":
          return subargs ? arena.joinCommunity(subargs) : "Usage: /arena join <communityId>";
        case "notifs":
          return arena.getNotifications(subargs || undefined);
        case "unseen":
          return arena.unseenNotifications();
        case "seen":
          return arena.markAllSeen();
        case "config":
          return arena.arenaConfig();
        case "profile":
          return arena.getProfile();
        case "update": {
          const sp = subargs.split(/\s+/, 2);
          const field = sp[0]?.toLowerCase();
          const val = subargs.slice((sp[0]?.length ?? 0)).trim();
          if (!field || !val) return "Usage: /arena update <name|bio> <value>";
          if (field === "name") return arena.updateProfile(val);
          if (field === "bio") return arena.updateProfile(undefined, val);
          return "Fields: name, bio";
        }
        case "register": {
          const sp = subargs.split(/\s+/, 3);
          if (!sp[0] || !sp[1] || !sp[2]) return "Usage: /arena register <name> <handle> <bio>";
          return arena.registerAgent(sp[0], sp[1], subargs.slice(sp[0].length + sp[1].length + 2).trim());
        }
        default:
          return "Arena commands: post, reply, quote, like, unlike, repost, search, user, trending, follow, unfollow, followers, dm, convos, react, stage, live, stages, lives, shares, holdings, earnings, communities, csearch, join, notifs, unseen, seen, profile, update, register, config";
      }
    }

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
