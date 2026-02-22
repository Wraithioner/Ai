/** Git skills — repo management from Telegram. */

import { exec } from "child_process";
import { shellEscape } from "../utils/sanitize.js";
import { REPOS_DIR, TIMEOUT_SHELL } from "../utils/constants.js";

function git(args: string, cwd?: string): Promise<string> {
  const cmd = `git ${args}`;
  return new Promise((resolve) => {
    exec(cmd, { timeout: TIMEOUT_SHELL, cwd: cwd ?? process.cwd() }, (error, stdout, stderr) => {
      const out = stdout.trim();
      const err = stderr.trim();
      if (error && !out && !err) {
        resolve(`Error: ${error.message}`);
        return;
      }
      if (out && err) resolve(`${out}\n${err}`);
      else resolve(out || err || "Done.");
    });
  });
}

export function gitStatus(cwd?: string): Promise<string> {
  return git("status --short", cwd);
}

export function gitLog(count = 10, cwd?: string): Promise<string> {
  return git(`log --oneline -${count}`, cwd);
}

export function gitDiff(cwd?: string): Promise<string> {
  return git("diff --stat", cwd);
}

export function gitClone(url: string): Promise<string> {
  return git(`clone ${shellEscape(url)}`, REPOS_DIR);
}

export function gitPull(cwd?: string): Promise<string> {
  return git("pull", cwd);
}

export function gitBranch(cwd?: string): Promise<string> {
  return git("branch -a", cwd);
}
