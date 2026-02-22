"""Execute Python code snippets with restricted builtins."""

import sys
import io
import contextlib

# Restricted builtins — block filesystem, imports, and system access
SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "chr": chr, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hash": hash, "hex": hex, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len, "list": list,
    "map": map, "max": max, "min": min, "next": next, "oct": oct,
    "ord": ord, "pow": pow, "print": print, "range": range,
    "repr": repr, "reversed": reversed, "round": round, "set": set,
    "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
    "Exception": Exception, "ValueError": ValueError,
    "TypeError": TypeError, "KeyError": KeyError,
    "IndexError": IndexError, "RuntimeError": RuntimeError,
}


def main():
    if len(sys.argv) < 2:
        print("No code provided.")
        return

    code = sys.argv[1]

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, {"__builtins__": SAFE_BUILTINS}, {})

        output = stdout_capture.getvalue().strip()
        errors = stderr_capture.getvalue().strip()

        if output:
            print(output[:4000])
        if errors:
            print(f"[stderr] {errors[:1000]}")
        if not output and not errors:
            print("(no output)")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
