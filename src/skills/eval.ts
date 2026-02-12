/** Native JavaScript evaluation — no Python bridge overhead. */

import vm from "vm";
import util from "util";

export function evalJS(code: string): string {
  const sandbox = {
    console: {
      log: (...args: any[]) => { output.push(args.map(formatValue).join(" ")); },
      error: (...args: any[]) => { output.push("[err] " + args.map(formatValue).join(" ")); },
      warn: (...args: any[]) => { output.push("[warn] " + args.map(formatValue).join(" ")); },
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
    setTimeout: undefined,
    setInterval: undefined,
    process: undefined,
    require: undefined,
  };

  const output: string[] = [];

  try {
    const context = vm.createContext(sandbox);
    const result = vm.runInContext(code, context, {
      timeout: 5_000,
      filename: "eval.js",
    });

    if (result !== undefined) {
      output.push(formatValue(result));
    }

    return output.join("\n").slice(0, 4000) || "(no output)";
  } catch (e: any) {
    if (e.code === "ERR_SCRIPT_EXECUTION_TIMEOUT") {
      return "Execution timed out (5s limit).";
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
