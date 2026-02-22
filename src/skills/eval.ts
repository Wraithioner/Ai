/** Native JavaScript evaluation — no Python bridge overhead. */

import vm from "vm";
import util from "util";
import { TIMEOUT_EVAL, MAX_RESPONSE } from "../utils/constants.js";

export function evalJS(code: string): string {
  const output: string[] = [];

  const sandbox = {
    console: {
      log: (...args: any[]) => { output.push(args.map(formatValue).join(" ")); },
      error: (...args: any[]) => { output.push("[err] " + args.map(formatValue).join(" ")); },
      warn: (...args: any[]) => { output.push("[warn] " + args.map(formatValue).join(" ")); },
      info: (...args: any[]) => { output.push("[info] " + args.map(formatValue).join(" ")); },
    },
    Math,
    Date,
    JSON,
    Array,
    Object,
    String,
    Number,
    Boolean,
    RegExp,
    Map,
    Set,
    Promise,
    parseInt,
    parseFloat,
    isNaN,
    isFinite,
    encodeURIComponent,
    decodeURIComponent,
    encodeURI,
    decodeURI,
    atob: (s: string) => Buffer.from(s, "base64").toString("utf-8"),
    btoa: (s: string) => Buffer.from(s, "utf-8").toString("base64"),
    setTimeout: undefined,
    setInterval: undefined,
    process: undefined,
    require: undefined,
    fetch: undefined,
    globalThis: undefined,
    global: undefined,
  };

  try {
    const context = vm.createContext(sandbox);
    const result = vm.runInContext(code, context, {
      timeout: TIMEOUT_EVAL,
      filename: "eval.js",
    });

    if (result !== undefined) {
      output.push(formatValue(result));
    }

    return output.join("\n").slice(0, MAX_RESPONSE) || "(no output)";
  } catch (e: any) {
    if (e.code === "ERR_SCRIPT_EXECUTION_TIMEOUT") {
      return `Execution timed out (${TIMEOUT_EVAL / 1000}s limit).`;
    }
    return `Error: ${e.message}`;
  }
}

function formatValue(val: any): string {
  if (val === undefined) return "undefined";
  if (val === null) return "null";
  if (typeof val === "string") return val;
  return util.inspect(val, { depth: 3, colors: false, maxStringLength: 500 });
}
