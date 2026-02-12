/** Python bridge — execute Python scripts from TypeScript. */

import { exec } from "child_process";
import { shellEscape } from "./sanitize.js";

export function runPython(script: string, args: string[] = []): Promise<string> {
  const escaped = args.map((a) => shellEscape(a)).join(" ");
  const cmd = `python3 python/skills/${script} ${escaped}`;

  return new Promise((resolve) => {
    exec(cmd, { timeout: 30_000, cwd: process.cwd() }, (error, stdout, stderr) => {
      if (error) {
        resolve(`Error: ${error.message}`);
        return;
      }
      const output = stdout.trim();
      const errors = stderr.trim();
      if (output && errors) resolve(`${output}\n[stderr] ${errors}`);
      else if (errors) resolve(`[stderr] ${errors}`);
      else resolve(output || "Done (no output)");
    });
  });
}
