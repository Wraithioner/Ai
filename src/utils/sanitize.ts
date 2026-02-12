/** Input sanitization and security utilities. */

/** Sensitive env var patterns that should never be exposed. */
const SENSITIVE_PATTERNS = [
  /token/i, /secret/i, /password/i, /pass/i, /key/i,
  /auth/i, /credential/i, /smtp/i, /api/i, /private/i,
];

/** Check if an env var name is sensitive. */
export function isSensitiveEnv(name: string): boolean {
  return SENSITIVE_PATTERNS.some((p) => p.test(name));
}

/** Get a safe env var value — masks sensitive ones. */
export function safeEnvValue(name: string): string {
  const val = process.env[name];
  if (!val) return `${name} not set`;
  if (isSensitiveEnv(name)) return `${name} = ****${val.slice(-4)}`;
  return `${name} = ${val}`;
}

/** List all non-sensitive env vars. */
export function listSafeEnvVars(): string {
  return Object.keys(process.env)
    .sort()
    .map((k) => {
      if (isSensitiveEnv(k)) return `${k} = [REDACTED]`;
      const val = process.env[k] ?? "";
      return `${k} = ${val.length > 80 ? val.slice(0, 80) + "..." : val}`;
    })
    .join("\n");
}

/** Sanitize a filename to prevent path traversal. */
export function sanitizeFilename(name: string): string {
  return name.replace(/\.\./g, "").replace(/[\/\\]/g, "_");
}

/** Escape Markdown special characters for Telegram. */
export function escapeMarkdown(text: string): string {
  return text.replace(/([_*\[\]()~`>#+\-=|{}.!])/g, "\\$1");
}

/** Wrap output in a code block for safe Telegram display. */
export function codeBlock(text: string, lang = ""): string {
  const escaped = text.replace(/`/g, "'");
  return `\`\`\`${lang}\n${escaped}\n\`\`\``;
}
