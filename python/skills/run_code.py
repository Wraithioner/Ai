"""Execute Python code snippets safely."""

import sys
import io
import contextlib

def main():
    if len(sys.argv) < 2:
        print("No code provided.")
        return

    code = sys.argv[1]

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, {"__builtins__": __builtins__}, {})

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
