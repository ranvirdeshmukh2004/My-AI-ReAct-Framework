"""
python_tool.py — Sandboxed Python Execution
==============================================
Runs model-written Python in a locked-down subprocess.

Defence in depth, because a substring blocklist is not security:

1. **AST validation** — the code is parsed and walked before it ever runs.
   Imports are checked against an allowlist, and the dunder-attribute
   escape chain (``().__class__.__bases__[0].__subclasses__()``) is
   rejected outright.
2. **Process isolation** — execution happens in a fresh subprocess with a
   scrubbed environment, so nothing it does can touch the agent process.
3. **Resource limits** — CPU seconds, address space and file size are
   capped via ``resource`` inside the child, so a fork bomb or a runaway
   allocation cannot take the host down.
4. **Wall-clock timeout** — the parent kills the whole process group if
   the child outlives its budget.

The executor is REPL-like: a trailing bare expression is displayed
automatically, so ``2 + 2`` returns ``4`` without an explicit ``print``.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile

from tools.base import Tool
from tools.common import ToolError, clean_input, truncate

# ============================================
# Policy
# ============================================

TIMEOUT_SECONDS = 15
MAX_MEMORY_MB = 512
MAX_OUTPUT_CHARS = 6000

# Modules the sandbox may import. Everything here is computation-only: no
# filesystem, no network, no process control.
ALLOWED_IMPORTS = {
    # numeric & scientific
    "math", "cmath", "statistics", "decimal", "fractions", "random",
    "numpy", "np", "pandas", "pd",
    # data structures & functional
    "collections", "itertools", "functools", "operator", "heapq", "bisect",
    "array", "copy", "enum", "dataclasses", "typing", "numbers",
    # text & encoding
    "re", "string", "textwrap", "unicodedata", "json", "csv", "io",
    "base64", "binascii", "hashlib", "hmac", "uuid", "struct", "zlib",
    # time
    "datetime", "time", "calendar", "zoneinfo",
    # misc
    "pprint", "reprlib", "secrets", "difflib", "graphlib", "abc",
}

# Names that hand back interpreter internals or I/O.
BANNED_NAMES = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "memoryview", "breakpoint", "exit", "quit", "help",
    "__builtins__", "__loader__", "__spec__",
}

# Dunder attributes that are harmless to touch. Anything else with a
# double-underscore name is the start of a sandbox escape.
ALLOWED_DUNDER_ATTRS = {
    "__name__", "__doc__", "__len__", "__str__", "__repr__",
    "__version__", "__file__", "__all__",
}


class _UnsafeCode(Exception):
    """Raised by the validator when the AST contains something disallowed."""


def _validate(tree: ast.AST) -> None:
    """
    Walk the AST and reject anything outside the sandbox policy.

    Operating on the parsed tree (rather than the source text) is what makes
    this robust: ``__import__`` assembled from string fragments still shows
    up as a Name/Attribute node here, and a module name inside a comment or
    string literal is simply not an Import node at all.
    """
    for node in ast.walk(tree):
        # --- imports ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    raise _UnsafeCode(
                        f"import of '{alias.name}' is not permitted in the sandbox"
                    )

        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level:  # relative import
                raise _UnsafeCode("relative imports are not permitted")
            if root not in ALLOWED_IMPORTS:
                raise _UnsafeCode(
                    f"import from '{node.module}' is not permitted in the sandbox"
                )

        # --- dangerous builtins referenced by name ---
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                raise _UnsafeCode(f"use of '{node.id}' is not permitted")

        # --- dunder attribute traversal (the classic escape chain) ---
        elif isinstance(node, ast.Attribute):
            attr = node.attr
            if attr.startswith("__") and attr.endswith("__"):
                if attr not in ALLOWED_DUNDER_ATTRS:
                    raise _UnsafeCode(
                        f"access to '{attr}' is not permitted "
                        "(interpreter internals are off limits)"
                    )

        # --- with-statement on banned context managers is caught by Name ---

    return None


# The preamble runs inside the child. It clamps resources, then execs the
# user's code so limits are already in force before any of it runs.
_CHILD_PREAMBLE = f"""
import resource, sys

_MB = 1024 * 1024
try:
    resource.setrlimit(resource.RLIMIT_CPU, ({TIMEOUT_SECONDS}, {TIMEOUT_SECONDS}))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_AS, ({MAX_MEMORY_MB} * _MB, {MAX_MEMORY_MB} * _MB))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
except (ValueError, OSError):
    pass
try:
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
except (ValueError, OSError):
    pass

sys.setrecursionlimit(3000)
"""


def _wrap_last_expression(code: str, tree: ast.Module) -> str:
    """
    Echo a trailing bare expression, the way a REPL would.

    Models often write ``df.describe()`` as the last line and expect to see
    it. Without this they get empty output and burn a step adding print().
    """
    if not tree.body:
        return code

    last = tree.body[-1]
    if not isinstance(last, ast.Expr):
        return code

    # Already a print(...) call — leave it alone.
    if (isinstance(last.value, ast.Call)
            and isinstance(last.value.func, ast.Name)
            and last.value.func.id == "print"):
        return code

    lines = code.splitlines()
    start = last.lineno - 1
    end = last.end_lineno or last.lineno

    expr_src = "\n".join(lines[start:end])
    # Only wrap a single-line expression at zero indentation; anything else
    # risks corrupting the source.
    if len(expr_src.splitlines()) != 1 or expr_src[:1].isspace():
        return code

    lines[start:end] = [f"__result__ = ({expr_src.strip()})",
                        "if __result__ is not None: print(repr(__result__))"]
    return "\n".join(lines)


def execute_python(code: str) -> str:
    """
    Validate and run Python code in an isolated subprocess.

    Args:
        code: Python source. Markdown fences are stripped automatically.

    Returns:
        Captured stdout (plus stderr on failure), or an explanatory error.
    """
    source = clean_input(code, strip_fences=True)
    if not source:
        return str(ToolError("No code provided.",
                             "Pass Python source, e.g. 'print(sum(range(10)))'."))

    # --- parse ---
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        return str(ToolError(
            f"Syntax error on line {exc.lineno}: {exc.msg}",
            "Check quotes, colons and indentation.",
        ))

    # --- policy check ---
    try:
        _validate(tree)
    except _UnsafeCode as exc:
        return str(ToolError(
            f"Blocked for safety: {exc}",
            "The sandbox allows pure computation only — math, statistics, "
            "numpy, pandas, json, re, datetime and similar. Filesystem, "
            "network and process access are unavailable.",
        ))

    source = _wrap_last_expression(source, tree)
    program = _CHILD_PREAMBLE + "\n" + source

    # --- execute ---
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8",
        ) as handle:
            handle.write(program)
            temp_path = handle.name

        # A scrubbed environment: no inherited API keys, no PYTHONPATH.
        child_env = {
            "PATH": "/usr/bin:/bin",
            "HOME": tempfile.gettempdir(),
            "LANG": "en_US.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        }

        completed = subprocess.run(
            # -I isolates the interpreter (ignores PYTHONPATH and the user
            # site dir) while still loading site-packages, so the advertised
            # numpy/pandas remain importable.
            [sys.executable, "-I", temp_path],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=child_env,
            cwd=tempfile.gettempdir(),
            start_new_session=True,   # isolate the process group for clean kills
        )
    except subprocess.TimeoutExpired:
        return str(ToolError(
            f"Execution exceeded the {TIMEOUT_SECONDS}s limit.",
            "Reduce the input size or avoid unbounded loops.",
        ))
    except Exception as exc:
        return str(ToolError(f"Could not run the code: {exc}"))
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return _format_output(completed)


def _format_output(completed: subprocess.CompletedProcess) -> str:
    """Turn the child's streams into one readable observation."""
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = _last_traceback_line(stderr) or stderr or "unknown error"
        out = f"❌ Python error: {detail}"
        if stdout:
            out += f"\n\n--- output before the error ---\n{truncate(stdout, 1500)}"
        return out

    if not stdout:
        return "(ran successfully, but produced no output — add a print() to see values)"

    return truncate(stdout, MAX_OUTPUT_CHARS, note="print less to see it all")


def _last_traceback_line(stderr: str) -> str:
    """
    Extract just the exception line from a traceback.

    The intermediate frames all point into the temp file and the preamble,
    which is noise the model cannot act on.
    """
    if not stderr:
        return ""
    lines = [ln for ln in stderr.strip().splitlines() if ln.strip()]
    for line in reversed(lines):
        if not line.startswith((" ", "\t", "Traceback")):
            return line.strip()
    return lines[-1].strip() if lines else ""


python_tool = Tool(
    name="python_executor",
    description=(
        "Run Python for data analysis, algorithms, string processing and "
        "multi-step computation. numpy and pandas are available, plus math, "
        "statistics, json, re, datetime, itertools, collections and hashlib. "
        "A trailing bare expression is printed automatically. "
        f"Runs in a sandbox with a {TIMEOUT_SECONDS}s limit and no filesystem "
        "or network access. Input is Python source code."
    ),
    function=execute_python,
)
