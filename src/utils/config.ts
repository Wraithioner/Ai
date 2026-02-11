/** Configuration — reads from Railway environment variables. */

export const config = {
  telegramToken: process.env.TELEGRAM_BOT_TOKEN ?? "",
  ownerId: Number(process.env.OWNER_ID ?? "0"),
  aiProvider: process.env.AI_PROVIDER ?? "none",
  aiApiKey: process.env.AI_API_KEY ?? "",
  dataDir: process.env.DATA_DIR ?? "/app/data",
};
