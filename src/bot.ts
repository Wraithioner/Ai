/** Telegram bot gateway — connects grammY to the agent router. */

import { Bot, InputFile } from "grammy";
import fs from "fs";
import path from "path";
import { config } from "./utils/config.js";
import { route, HELP } from "./router.js";
import { persona } from "./personality.js";
import * as scheduler from "./skills/scheduler.js";
import * as cronSkill from "./skills/cron.js";
import { checkRateLimit } from "./utils/ratelimit.js";

const MAX_MSG = 4096;
const UPLOAD_DIR = process.env.UPLOAD_DIR ?? "/app/data/uploads";

export function createBot(): Bot {
  if (!config.telegramToken) {
    throw new Error("TELEGRAM_BOT_TOKEN not set. Add it in Railway env vars.");
  }

  const bot = new Bot(config.telegramToken);

  // --- Global error handler (prevents crashes) ---
  bot.catch((err) => {
    console.error(`[ERROR] ${err.message}`);
    const ctx = err.ctx;
    try {
      ctx.reply("Something broke internally. I'm still running though.").catch(() => {});
    } catch { /* can't reply, just log */ }
  });

  // --- Auth middleware ---
  bot.use(async (ctx, next) => {
    const userId = ctx.from?.id ?? 0;
    if (config.ownerId !== 0 && userId !== config.ownerId) {
      await ctx.reply(persona.responses.unauthorized, { parse_mode: "Markdown" });
      return;
    }
    await next();
  });

  // --- Rate limiting middleware ---
  bot.use(async (ctx, next) => {
    const userId = ctx.from?.id ?? 0;
    const { allowed, remaining } = checkRateLimit(userId);
    if (!allowed) {
      await ctx.reply(`Slow down. Rate limited — try again in ${remaining}s.`);
      return;
    }
    await next();
  });

  // --- /start ---
  bot.command("start", async (ctx) => {
    const name = ctx.from?.first_name ?? "boss";
    const welcome = persona.welcome(name);
    await sendSafe(ctx, `${welcome}\n\n${HELP}`);
  });

  // --- /help ---
  bot.command("help", async (ctx) => {
    await sendSafe(ctx, `${persona.helpHeader()}\n${HELP}`);
  });

  // --- /id ---
  bot.command("id", async (ctx) => {
    const u = ctx.from;
    await sendSafe(
      ctx,
      `Your Telegram ID: \`${u?.id}\`\nName: ${u?.first_name ?? ""} ${u?.last_name ?? ""}\nUsername: @${u?.username ?? "none"}`
    );
  });

  // --- File uploads from user ---
  bot.on("message:document", async (ctx) => {
    await handleMediaUpload(ctx, "document");
  });

  // --- Photo uploads ---
  bot.on("message:photo", async (ctx) => {
    await handleMediaUpload(ctx, "photo");
  });

  // --- Voice messages ---
  bot.on("message:voice", async (ctx) => {
    await handleMediaUpload(ctx, "voice");
  });

  // --- Video messages ---
  bot.on("message:video", async (ctx) => {
    await handleMediaUpload(ctx, "video");
  });

  // --- /sendfile command ---
  bot.command("sendfile", async (ctx) => {
    const filePath = ctx.message?.text?.split(/\s+/, 2)[1]?.trim();
    if (!filePath) {
      await ctx.reply("Usage: `/sendfile <path>`", { parse_mode: "Markdown" });
      return;
    }
    try {
      if (!fs.existsSync(filePath)) {
        await ctx.reply(`File not found: ${filePath}`);
        return;
      }
      const stat = fs.statSync(filePath);
      if (stat.size > 50 * 1024 * 1024) {
        await ctx.reply("File too large (max 50MB for Telegram).");
        return;
      }
      await ctx.replyWithDocument(new InputFile(filePath), {
        caption: `📄 ${path.basename(filePath)} (${(stat.size / 1024).toFixed(1)} KB)`,
      });
    } catch (e: any) {
      await ctx.reply(`Failed to send: ${e.message}`);
    }
  });

  // --- All other text messages ---
  bot.on("message:text", async (ctx) => {
    const text = ctx.message.text;
    const user = ctx.from?.username ?? String(ctx.from?.id ?? "unknown");
    console.log(`[${ctx.from?.id} @${user}] ${text}`);

    await ctx.replyWithChatAction("typing");

    if (text.startsWith("/")) {
      let response = await route(text, user);

      if (response === "__ID__") {
        const u = ctx.from;
        response = `Your Telegram ID: \`${u?.id}\`\nName: ${u?.first_name ?? ""} ${u?.last_name ?? ""}\nUsername: @${u?.username ?? "none"}`;
      }

      await sendSafe(ctx, response);
    } else {
      await sendSafe(ctx, persona.responses.echo(text));
    }
  });

  return bot;
}

/** Set up bot commands menu and start scheduler. */
export async function setupBot(bot: Bot) {
  const commands = [
    { command: "help", description: "Show all commands" },
    { command: "status", description: "Dashboard overview" },
    { command: "run", description: "Execute a shell command" },
    { command: "sysinfo", description: "System information" },
    { command: "ls", description: "List directory" },
    { command: "read", description: "Read a file" },
    { command: "fetch", description: "Fetch a webpage" },
    { command: "note", description: "Save a note" },
    { command: "notes", description: "List notes" },
    { command: "remind", description: "Set a reminder" },
    { command: "eval", description: "Run JavaScript" },
    { command: "py", description: "Run Python code" },
    { command: "git", description: "Git operations" },
    { command: "email", description: "Send an email" },
    { command: "sendfile", description: "Send a file from server" },
    { command: "ping", description: "Ping (or check bot)" },
    { command: "id", description: "Your Telegram ID" },
    { command: "history", description: "Command history" },
    { command: "grep", description: "Search file contents" },
    { command: "cron", description: "Recurring task" },
    { command: "alias", description: "Create shortcut" },
  ];
  await bot.api.setMyCommands(commands);
  console.log(`${persona.name} commands menu set.`);

  // Start reminder scheduler
  scheduler.registerCallback(async (message: string) => {
    if (config.ownerId === 0) return;
    try {
      await bot.api.sendMessage(config.ownerId, persona.responses.reminder(message), {
        parse_mode: "Markdown",
      });
      console.log(`Reminder sent: ${message}`);
    } catch (e) {
      console.error("Failed to send reminder:", e);
    }
  });
  scheduler.startScheduler();

  // Start cron scheduler
  cronSkill.registerCronCallback(async (command: string) => {
    if (config.ownerId === 0) return;
    try {
      const { route } = await import("./router.js");
      const result = await route(command, "cron");
      await bot.api.sendMessage(
        config.ownerId,
        `*Cron executed:* \`${command}\`\n\n${result}`,
        { parse_mode: "Markdown" }
      );
    } catch (e) {
      console.error("Cron execution failed:", e);
    }
  });
  cronSkill.startCronScheduler();
  console.log("Schedulers started.");
}

/** Handle media uploads (documents, photos, voice, video). */
async function handleMediaUpload(ctx: any, type: string) {
  try {
    await ctx.replyWithChatAction("typing");
    const tgFile = await ctx.getFile();
    const filePath = tgFile.file_path;
    if (!filePath) {
      await ctx.reply("Couldn't get file path.");
      return;
    }

    fs.mkdirSync(UPLOAD_DIR, { recursive: true });

    let filename: string;
    if (type === "document") {
      filename = ctx.message.document?.file_name ?? `doc_${Date.now()}`;
    } else if (type === "photo") {
      filename = `photo_${Date.now()}.jpg`;
    } else if (type === "voice") {
      filename = `voice_${Date.now()}.ogg`;
    } else if (type === "video") {
      filename = `video_${Date.now()}.mp4`;
    } else {
      filename = `file_${Date.now()}`;
    }

    const dest = path.join(UPLOAD_DIR, filename);
    const url = `https://api.telegram.org/file/bot${config.telegramToken}/${filePath}`;
    const res = await fetch(url);
    const buffer = Buffer.from(await res.arrayBuffer());
    fs.writeFileSync(dest, buffer);

    const sizeKB = (buffer.length / 1024).toFixed(1);
    await sendSafe(ctx, `${type.charAt(0).toUpperCase() + type.slice(1)} saved: \`${dest}\`\nSize: ${sizeKB} KB`);
  } catch (e: any) {
    await ctx.reply(`Upload failed: ${e.message}`);
  }
}

/** Send a message, splitting if too long. Falls back to plain text on parse error. */
async function sendSafe(ctx: any, text: string) {
  const chunks: string[] = [];
  for (let i = 0; i < text.length; i += MAX_MSG) {
    chunks.push(text.slice(i, i + MAX_MSG));
  }

  for (const chunk of chunks) {
    try {
      await ctx.reply(chunk, { parse_mode: "Markdown" });
    } catch {
      try {
        await ctx.reply(chunk);
      } catch (e) {
        console.error("[sendSafe] Failed to send message:", e);
      }
    }
  }
}
