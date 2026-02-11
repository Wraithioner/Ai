/** Entry point — start the agent. */

import { createBot, setupBot } from "./bot.js";
import { persona } from "./personality.js";

async function main() {
  console.log(persona.status.booting());

  const bot = createBot();
  await setupBot(bot);

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
