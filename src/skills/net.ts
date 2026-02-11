/** Network skills — fetch, download, ping, DNS. */

import { exec } from "child_process";
import fs from "fs";
import path from "path";
import https from "https";
import http from "http";

const DOWNLOAD_DIR = process.env.DOWNLOAD_DIR ?? "/app/data/downloads";

export async function fetchUrl(url: string): Promise<string> {
  if (!url.startsWith("http")) url = "https://" + url;

  return new Promise((resolve) => {
    const mod = url.startsWith("https") ? https : http;
    const req = mod.get(url, { timeout: 10_000, headers: { "User-Agent": "Agent/0.1" } }, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        resolve(`Redirect → ${res.headers.location}`);
        return;
      }

      let data = "";
      res.setEncoding("utf-8");
      res.on("data", (chunk) => {
        data += chunk;
        if (data.length > 10_000) res.destroy();
      });
      res.on("end", () => {
        const ct = res.headers["content-type"] ?? "";
        if (ct.includes("text/html")) {
          resolve(stripHtml(data).slice(0, 4000));
        } else {
          resolve(data.slice(0, 4000));
        }
      });
    });
    req.on("error", (e) => resolve(`Error: ${e.message}`));
    req.on("timeout", () => {
      req.destroy();
      resolve("Request timed out.");
    });
  });
}

export async function downloadFile(url: string, filename?: string): Promise<string> {
  if (!url.startsWith("http")) url = "https://" + url;
  if (!filename) {
    const u = new URL(url);
    filename = path.basename(u.pathname) || "download";
  }

  fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });
  const dest = path.join(DOWNLOAD_DIR, filename);

  return new Promise((resolve) => {
    const mod = url.startsWith("https") ? https : http;
    const req = mod.get(url, { timeout: 30_000, headers: { "User-Agent": "Agent/0.1" } }, (res) => {
      if (res.statusCode !== 200) {
        resolve(`HTTP ${res.statusCode}`);
        return;
      }
      const file = fs.createWriteStream(dest);
      let bytes = 0;
      res.on("data", (chunk: Buffer) => { bytes += chunk.length; });
      res.pipe(file);
      file.on("finish", () => {
        file.close();
        resolve(`Downloaded: ${filename} (${formatBytes(bytes)})\nSaved to: ${dest}`);
      });
    });
    req.on("error", (e) => resolve(`Error: ${e.message}`));
  });
}

export function listDownloads(): string {
  try {
    if (!fs.existsSync(DOWNLOAD_DIR)) return "No downloads yet.";
    const files = fs.readdirSync(DOWNLOAD_DIR);
    if (files.length === 0) return "No downloads yet.";
    return files
      .map((f) => {
        const stat = fs.statSync(path.join(DOWNLOAD_DIR, f));
        return `📄 ${f}  (${formatBytes(stat.size)})`;
      })
      .join("\n");
  } catch (e: any) {
    return `Error: ${e.message}`;
  }
}

export function ping(host: string): Promise<string> {
  return new Promise((resolve) => {
    exec(`ping -c 4 ${host}`, { timeout: 10_000 }, (error, stdout) => {
      if (error) resolve(`Ping failed: ${error.message}`);
      else resolve(stdout.trim());
    });
  });
}

export function dnsLookup(domain: string): Promise<string> {
  return new Promise((resolve) => {
    exec(`dig +short ${domain}`, { timeout: 5_000 }, (error, stdout) => {
      if (error) resolve(`DNS lookup failed: ${error.message}`);
      else resolve(stdout.trim() || "No records found.");
    });
  });
}

export function curl(url: string): Promise<string> {
  return new Promise((resolve) => {
    exec(`curl -sI '${url}' | head -20`, { timeout: 10_000 }, (error, stdout) => {
      if (error) resolve(`Curl failed: ${error.message}`);
      else resolve(stdout.trim());
    });
  });
}

function stripHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function formatBytes(bytes: number): string {
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}
