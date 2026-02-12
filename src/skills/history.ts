/** Command history — tracks recent commands. */

interface HistoryEntry {
  command: string;
  timestamp: number;
  user: string;
}

const MAX_HISTORY = 50;
const entries: HistoryEntry[] = [];

export function record(command: string, user: string) {
  entries.push({ command, timestamp: Date.now(), user });
  if (entries.length > MAX_HISTORY) entries.shift();
}

export function getHistory(count = 20): string {
  if (entries.length === 0) return "No command history yet.";

  const shown = entries.slice(-count).reverse();
  return shown
    .map((e, i) => {
      const time = new Date(e.timestamp).toLocaleTimeString();
      return `${i + 1}. \`${e.command}\` — ${time}`;
    })
    .join("\n");
}

export function clearHistory(): string {
  entries.length = 0;
  return "History cleared.";
}
