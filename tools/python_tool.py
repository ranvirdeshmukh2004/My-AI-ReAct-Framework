"""
python_tool.py — Sandboxed Python Execution
==============================================
Executes Python code in a separate subprocess with:
- 10-second timeout (prevents infinite loops)
- Restricted imports (no os, sys, subprocess, etc.)
- Captured stdout and stderr

This is useful for data analysis, quick computations,
and code demonstrations.
"""

import subprocess
import tempfile
import os
from tools.base import Tool

# ============================================
# Blocked imports for security
# ============================================

BLOCKED_IMPORTS = [
    "os", "sys", "subprocess", "shutil",
    "pathlib", "socket", "http", "urllib",
    "requests", "pickle", "ctypes",
    "importlib", "signal", "__import__",
]

TIMEOUT_SECONDS = 10


def execute_python(code: str) -> str:
    """
    Execute Python code in a sandboxed subprocess.
    
    Args:
        code: Python code string to execute.
    
    Returns:
        The stdout output of the code, or error messages.
    """
    code = code.strip()

    # Remove markdown code fences if present
    if code.startswith("```python"):
        code = code[len("```python"):].strip()
    if code.startswith("```"):
        code = code[3:].strip()
    if code.endswith("```"):
        code = code[:-3].strip()

    # Security check: block dangerous imports
    for blocked in BLOCKED_IMPORTS:
        if f"import {blocked}" in code or f"from {blocked}" in code:
            return f"⚠️ Security Error: Import '{blocked}' is not allowed for safety reasons."

    # Also block exec/eval calls within the code
    if "exec(" in code or "eval(" in code or "__import__" in code:
        return "⚠️ Security Error: exec(), eval(), and __import__() are not allowed."

    try:
        # Write code to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            dir=tempfile.gettempdir(),
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Execute in a subprocess with timeout
            result = subprocess.run(
                ["python3", temp_path],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                # Only include stderr if there's an actual error
                if result.returncode != 0:
                    output += f"\nError:\n{result.stderr}"

            if not output.strip():
                output = "(Code executed successfully with no output)"

            return output.strip()

        finally:
            # Clean up the temporary file
            os.unlink(temp_path)

    except subprocess.TimeoutExpired:
        return f"⏰ Timeout Error: Code execution exceeded {TIMEOUT_SECONDS} seconds. Please simplify your code."

    except Exception as e:
        return f"Execution error: {str(e)}"


# ============================================
# Register as a Tool
# ============================================

python_tool = Tool(
    name="python_executor",
    description=(
        "Execute Python code and return the output. "
        "Use this for data analysis, calculations, string manipulation, "
        "or any task that benefits from running actual Python code. "
        "Input should be valid Python code. "
        "Note: Some imports are restricted for security (no os, sys, subprocess, etc.). "
        "Code has a 10-second timeout."
    ),
    function=execute_python,
)
