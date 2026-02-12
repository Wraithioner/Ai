/** Entry point — start the agent. */

import { createBot, setupBot } from "./bot.js";
import { persona } from "./personality.js";
import { stopScheduler } from "./skills/scheduler.js";
import { stopCronScheduler } from "./skills/cron.js";

async function main() {
  console.log(persona.status.booting());

  const bot = createBot();
  await setupBot(bot);

  // Graceful shutdown
  const shutdown = () => {
    console.log(persona.status.shutdown());
    stopScheduler();
    stopCronScheduler();
    bot.stop();
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
  process.on("unhandledRejection", (err) => {
    console.error("[UNHANDLED REJECTION]", err);
  });

  console.log(persona.status.online());
  bot.start({
    drop_pending_updates: true,
    onStart: () => console.log(`${persona.name} connected to Telegram. Ready.`),
  });
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
