/** File management skills. */

import fs from "fs";
import path from "path";
import {
  WORKSPACE,
  MAX_FILE_READ,
  MAX_SEARCH_DEPTH,
  MAX_SEARCH_RESULTS,
} from "../utils/constants.js";

function resolve(p: string): string {
  if (path.isAbsolute(p)) return p;
  return path.join(WORKSPACE, p);
}

export function readFile(filePath: string): string {
  try {
    const target = resolve(filePath);
    if (!fs.existsSync(target)) return `File not found: ${filePath}`;
    const stat = fs.statSync(target);
    if (stat.size > MAX_FILE_READ) return `File too large (${stat.size} bytes). Use head instead.`;
    return fs.readFileSync(target, "utf-8");
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function writeFile(filePath: string, content: string): string {
  try {
    const target = resolve(filePath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, content);
    return `Wrote ${content.length} bytes to ${target}`;
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function listDir(dirPath = "."): string {
  try {
    const target = resolve(dirPath);
    if (!fs.existsSync(target)) return `Not found: ${dirPath}`;
    if (!fs.statSync(target).isDirectory()) return `Not a directory: ${dirPath}`;

    const entries = fs.readdirSync(target, { withFileTypes: true });
    if (entries.length === 0) return "(empty directory)";

    return entries
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((e) => {
        const prefix = e.isDirectory() ? "📁" : "📄";
        if (e.isFile()) {
          const size = fs.statSync(path.join(target, e.name)).size;
          return `${prefix} ${e.name}  (${formatSize(size)})`;
        }
        return `${prefix} ${e.name}/`;
      })
      .join("\n");
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function deleteFile(filePath: string): string {
  try {
    const target = resolve(filePath);
    if (!fs.existsSync(target)) return `Not found: ${filePath}`;
    if (fs.statSync(target).isDirectory()) return "Use rmdir for directories.";
    fs.unlinkSync(target);
    return `Deleted: ${target}`;
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function headFile(filePath: string, lines = 20): string {
  try {
    const target = resolve(filePath);
    if (!fs.existsSync(target)) return `File not found: ${filePath}`;
    const content = fs.readFileSync(target, "utf-8");
    const allLines = content.split("\n");
    const shown = allLines.slice(0, lines);
    let result = shown.join("\n");
    if (allLines.length > lines) {
      result += `\n... (${lines}/${allLines.length} lines shown)`;
    }
    return result;
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function searchFiles(dir: string, pattern: string): string {
  try {
    const target = resolve(dir);
    const results: string[] = [];
    walk(target, pattern, results, 0);
    if (results.length === 0) return `No files matching "${pattern}"`;
    return results.slice(0, MAX_SEARCH_RESULTS).join("\n");
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

function walk(dir: string, pattern: string, results: string[], depth: number) {
  if (depth > MAX_SEARCH_DEPTH || results.length >= MAX_SEARCH_RESULTS) return;
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.name === "node_modules") continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full, pattern, results, depth + 1);
      } else if (entry.name.toLowerCase().includes(pattern.toLowerCase())) {
        results.push(full);
      }
    }
  } catch { /* skip inaccessible dirs */ }
}

function formatSize(bytes: number): string {
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}
