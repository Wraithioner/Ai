/** Command aliases — create shortcuts for common commands. */

import fs from "fs";
import path from "path";

const DATA_DIR = process.env.DATA_DIR ?? "/app/data";
const ALIAS_FILE = path.join(DATA_DIR, "aliases.json");

function load(): Record<string, string> {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(ALIAS_FILE)) return {};
    return JSON.parse(fs.readFileSync(ALIAS_FILE, "utf-8"));
  } catch { return {}; }
}

function save(aliases: Record<string, string>) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(ALIAS_FILE, JSON.stringify(aliases, null, 2));
}

export function setAlias(name: string, command: string): string {
  if (name.startsWith("/")) name = name.slice(1);
  if (!name || !command) return "Usage: `/alias <name> <command>`";

  const aliases = load();
  aliases[name] = command;
  save(aliases);
  return `Alias set: \`/${name}\` → \`${command}\``;
}

export function removeAlias(name: string): string {
  if (name.startsWith("/")) name = name.slice(1);
  const aliases = load();
  if (!(name in aliases)) return `Alias \`${name}\` not found.`;
  delete aliases[name];
  save(aliases);
  return `Alias \`/${name}\` removed.`;
}

export function listAliases(): string {
  const aliases = load();
  const keys = Object.keys(aliases);
  if (keys.length === 0) return "No aliases set. Use `/alias <name> <command>` to create one.";
  return keys.map((k) => `/${k} → \`${aliases[k]}\``).join("\n");
}

export function resolveAlias(cmd: string): string | null {
  const name = cmd.startsWith("/") ? cmd.slice(1) : cmd;
  const aliases = load();
  return aliases[name] ?? null;
}
