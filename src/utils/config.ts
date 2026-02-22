/** Configuration — reads from environment variables. */

import { DATA_DIR } from "./constants.js";

export const config = {
  // Telegram
  telegramToken: process.env.TELEGRAM_BOT_TOKEN ?? "",
  ownerId: Number(process.env.OWNER_ID ?? "0"),

  // AI
  aiProvider: process.env.AI_PROVIDER ?? "none",
  aiApiKey: process.env.AI_API_KEY ?? "",

  // Arena
  arenaApiKey: process.env.ARENA_API_KEY ?? "",
  arenaAgentId: process.env.ARENA_AGENT_ID ?? "",
  arenaHandle: process.env.ARENA_HANDLE ?? "",
  arenaVerificationCode: process.env.ARENA_VERIFICATION_CODE ?? "",
  arenaWallet: process.env.ARENA_WALLET ?? "",
  arenaWalletPrivateKey: process.env.ARENA_WALLET_PRIVATE_KEY ?? "",

  // SMTP
  smtpHost: process.env.SMTP_HOST ?? "",
  smtpPort: Number(process.env.SMTP_PORT ?? "587"),
  smtpUser: process.env.SMTP_USER ?? "",
  smtpPass: process.env.SMTP_PASS ?? "",
  smtpFrom: process.env.SMTP_FROM ?? "",

  // Limits
  rateLimit: Number(process.env.RATE_LIMIT ?? "30"),

  // Paths
  dataDir: DATA_DIR,

  // Bot
  botName: process.env.BOT_NAME ?? "Atlas",
};
