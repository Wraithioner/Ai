/** Grep skill — search file contents. */

import fs from "fs";
import path from "path";

const WORKSPACE = process.env.WORKSPACE ?? "/app";

interface GrepResult {
  file: string;
  line: number;
  text: string;
}

export function grep(pattern: string, dir = ".", maxResults = 30): string {
  const target = path.isAbsolute(dir) ? dir : path.join(WORKSPACE, dir);

  if (!fs.existsSync(target)) return `Directory not found: ${dir}`;

  let regex: RegExp;
  try {
    regex = new RegExp(pattern, "i");
  } catch {
    return `Invalid regex pattern: ${pattern}`;
  }

  const results: GrepResult[] = [];
  searchDir(target, regex, results, maxResults, 0);

  if (results.length === 0) return `No matches for "${pattern}"`;

  return results
    .map((r) => `${r.file}:${r.line}: ${r.text.trim().slice(0, 120)}`)
    .join("\n");
}

function searchDir(dir: string, pattern: RegExp, results: GrepResult[], max: number, depth: number) {
  if (depth > 5 || results.length >= max) return;

  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch { return; }

  for (const entry of entries) {
    if (results.length >= max) break;
    if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist") continue;

    const full = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      searchDir(full, pattern, results, max, depth + 1);
    } else if (entry.isFile() && isTextFile(entry.name)) {
      try {
        const stat = fs.statSync(full);
        if (stat.size > 500_000) continue; // skip large files

        const content = fs.readFileSync(full, "utf-8");
        const lines = content.split("\n");
        for (let i = 0; i < lines.length && results.length < max; i++) {
          if (pattern.test(lines[i])) {
            results.push({ file: full, line: i + 1, text: lines[i] });
          }
        }
      } catch { /* skip unreadable files */ }
    }
  }
}

function isTextFile(name: string): boolean {
  const ext = path.extname(name).toLowerCase();
  const textExts = new Set([
    ".ts", ".js", ".py", ".json", ".yaml", ".yml", ".toml",
    ".md", ".txt", ".sh", ".bash", ".css", ".html", ".xml",
    ".env", ".cfg", ".ini", ".conf", ".log", ".csv",
  ]);
  return textExts.has(ext) || !ext; // no extension = probably text
}
