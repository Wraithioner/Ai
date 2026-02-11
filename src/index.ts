/** Entry point — start the agent. */

import { createBot, setupBot } from "./bot.js";

async function main() {
  console.log("Starting agent...");

  const bot = createBot();

  // Set up commands menu and scheduler before polling
  await setupBot(bot);

  // Start polling
  console.log("Bot is running. Polling for messages...");
  bot.start({
    drop_pending_updates: true,
    onStart: () => console.log("Bot connected to Telegram."),
  });
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
