/** Telegram bot gateway — connects grammY to the agent router. */

import { Bot } from "grammy";
import { config } from "./utils/config.js";
import { route, HELP } from "./router.js";
import * as scheduler from "./skills/scheduler.js";

const MAX_MSG = 4096;

export function createBot(): Bot {
  if (!config.telegramToken) {
    throw new Error("TELEGRAM_BOT_TOKEN not set. Add it in Railway env vars.");
  }

  const bot = new Bot(config.telegramToken);

  // --- Auth middleware ---
  bot.use(async (ctx, next) => {
    const userId = ctx.from?.id ?? 0;
    if (config.ownerId !== 0 && userId !== config.ownerId) {
      await ctx.reply(`Unauthorized. Your ID: \`${userId}\`\nSet OWNER_ID in Railway.`, {
        parse_mode: "Markdown",
      });
      return;
    }
    await next();
  });

  // --- /start and /help ---
  bot.command("start", async (ctx) => {
    const name = ctx.from?.first_name ?? "there";
    await sendSafe(ctx, `Hey **${name}**! I'm your personal agent.\n\n${HELP}`);
  });

  bot.command("help", async (ctx) => {
    await sendSafe(ctx, HELP);
  });

  // --- /id ---
  bot.command("id", async (ctx) => {
    const u = ctx.from;
    await sendSafe(
      ctx,
      `Your Telegram ID: \`${u?.id}\`\nName: ${u?.first_name ?? ""} ${u?.last_name ?? ""}\nUsername: @${u?.username ?? "none"}`
    );
  });

  // --- All other commands ---
  bot.on("message:text", async (ctx) => {
    const text = ctx.message.text;
    console.log(`[${ctx.from?.id} @${ctx.from?.username}] ${text}`);

    await ctx.replyWithChatAction("typing");

    if (text.startsWith("/")) {
      let response = await route(text);

      // Special case for /id (needs ctx)
      if (response === "__ID__") {
        const u = ctx.from;
        response = `Your Telegram ID: \`${u?.id}\`\nName: ${u?.first_name ?? ""} ${u?.last_name ?? ""}\nUsername: @${u?.username ?? "none"}`;
      }

      await sendSafe(ctx, response);
    } else {
      // Free-form text — placeholder for AI
      await sendSafe(
        ctx,
        `You said: "${text}"\n\nI can echo for now. Once an AI API is connected, I'll chat properly.\n\nType /help for commands.`
      );
    }
  });

  return bot;
}

/** Set up bot commands menu and start scheduler. */
export async function setupBot(bot: Bot) {
  const commands = [
    { command: "help", description: "Show all commands" },
    { command: "run", description: "Execute a shell command" },
    { command: "sysinfo", description: "System information" },
    { command: "ls", description: "List directory" },
    { command: "read", description: "Read a file" },
    { command: "fetch", description: "Fetch a webpage" },
    { command: "note", description: "Save a note" },
    { command: "notes", description: "List notes" },
    { command: "remind", description: "Set a reminder" },
    { command: "ping", description: "Ping (or check bot)" },
    { command: "id", description: "Your Telegram ID" },
    { command: "uptime", description: "Bot uptime" },
    { command: "py", description: "Run Python code" },
    { command: "git", description: "Git operations" },
  ];
  await bot.api.setMyCommands(commands);
  console.log("Bot commands menu set.");

  // Start reminder scheduler
  scheduler.registerCallback(async (message: string) => {
    if (config.ownerId === 0) return;
    try {
      await bot.api.sendMessage(config.ownerId, `**⏰ Reminder**\n\n${message}`, {
        parse_mode: "Markdown",
      });
      console.log(`Reminder sent: ${message}`);
    } catch (e) {
      console.error("Failed to send reminder:", e);
    }
  });
  scheduler.startScheduler();
  console.log("Scheduler started.");
}

/** Send a message, splitting if too long. */
async function sendSafe(ctx: any, text: string) {
  if (text.length <= MAX_MSG) {
    try {
      await ctx.reply(text, { parse_mode: "Markdown" });
    } catch {
      await ctx.reply(text);
    }
    return;
  }

  for (let i = 0; i < text.length; i += MAX_MSG) {
    const chunk = text.slice(i, i + MAX_MSG);
    try {
      await ctx.reply(chunk, { parse_mode: "Markdown" });
    } catch {
      await ctx.reply(chunk);
    }
  }
}
