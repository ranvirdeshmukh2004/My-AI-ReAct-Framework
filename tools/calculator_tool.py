"""
calculator_tool.py — Symbolic & Numeric Math
===============================================
A full computer-algebra front end built on sympy, with no ``eval()``
anywhere in the path.

Handles:
- Arithmetic & precision:   ``2**100``, ``22/7``, ``1e-9 + 1``
- Algebra:                  ``solve(x**2 - 4, x)``, ``factor(x**2-1)``
- Calculus:                 ``diff(x**3, x)``, ``integrate(sin(x), x)``,
                            ``limit(sin(x)/x, x, 0)``
- Linear algebra:           ``det([[1,2],[3,4]])``, ``inv(...)``
- Number theory:            ``isprime(97)``, ``factorint(360)``, ``gcd(12,18)``
- Statistics:               ``mean([1,2,3])``, ``stdev([...])``

Results are reported exactly *and* as a decimal when the two differ, which
is what makes the output actually useful to a downstream model.
"""

from __future__ import annotations

import re

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from tools.base import Tool
from tools.common import ToolError, clean_input

TRANSFORMATIONS = (
    standard_transformations
    + (implicit_multiplication_application, convert_xor)
)

# Symbols the parser should treat as free variables rather than errors.
_SYMBOLS = {name: sympy.Symbol(name) for name in
            ("x", "y", "z", "t", "n", "k", "a", "b", "c", "m", "p", "q", "r", "s")}


def _factorint(n):
    """Prime factorisation rendered readably: 360 -> 360 = 2^3 x 3^2 x 5."""
    value = sympy.Integer(n)
    factors = sympy.factorint(value)
    if not factors:
        return str(value)
    parts = [f"{p}^{e}" if e > 1 else f"{p}" for p, e in sorted(factors.items())]
    return f"{value} = " + " × ".join(parts)


def _matrix(rows):
    """Build a sympy Matrix from a nested list, for det/inv/rank helpers."""
    return sympy.Matrix(rows)


def _mean(values):
    seq = list(values)
    if not seq:
        raise ToolError("mean() needs at least one value.")
    return sympy.Rational(0) + sum(sympy.sympify(v) for v in seq) / len(seq)


def _stdev(values):
    seq = [sympy.sympify(v) for v in values]
    if len(seq) < 2:
        raise ToolError("stdev() needs at least two values.")
    mu = sum(seq) / len(seq)
    return sympy.sqrt(sum((v - mu) ** 2 for v in seq) / (len(seq) - 1))


def _median(values):
    seq = sorted(sympy.sympify(v) for v in values)
    if not seq:
        raise ToolError("median() needs at least one value.")
    mid = len(seq) // 2
    return seq[mid] if len(seq) % 2 else (seq[mid - 1] + seq[mid]) / 2


# The complete namespace available to expressions. Everything here is a sympy
# callable or constant — there is no builtin, no import, and no attribute
# access path back into the interpreter, which is what makes parse_expr safe.
_NAMESPACE: dict[str, object] = {
    # constants
    "pi": sympy.pi, "e": sympy.E, "E": sympy.E, "oo": sympy.oo,
    "inf": sympy.oo, "infinity": sympy.oo, "I": sympy.I, "j": sympy.I,
    # elementary
    "sqrt": sympy.sqrt, "cbrt": sympy.cbrt, "exp": sympy.exp,
    "log": sympy.log, "ln": sympy.log, "log10": lambda v: sympy.log(v, 10),
    "log2": lambda v: sympy.log(v, 2), "abs": sympy.Abs, "sign": sympy.sign,
    "floor": sympy.floor, "ceiling": sympy.ceiling, "ceil": sympy.ceiling,
    "round": lambda v, n=0: sympy.Float(v).round(int(n)),
    "factorial": sympy.factorial, "gamma": sympy.gamma,
    # trigonometry
    "sin": sympy.sin, "cos": sympy.cos, "tan": sympy.tan,
    "asin": sympy.asin, "acos": sympy.acos, "atan": sympy.atan,
    "atan2": sympy.atan2, "sinh": sympy.sinh, "cosh": sympy.cosh,
    "tanh": sympy.tanh, "deg": sympy.deg, "rad": sympy.rad,
    # algebra
    "solve": sympy.solve, "solveset": sympy.solveset, "nsolve": sympy.nsolve,
    "simplify": sympy.simplify, "expand": sympy.expand, "factor": sympy.factor,
    "cancel": sympy.cancel, "apart": sympy.apart, "together": sympy.together,
    "Eq": sympy.Eq, "roots": sympy.roots,
    # calculus
    "diff": sympy.diff, "derivative": sympy.diff, "integrate": sympy.integrate,
    "limit": sympy.limit, "series": sympy.series, "summation": sympy.summation,
    "Sum": sympy.Sum, "product": sympy.product,
    # number theory
    "gcd": sympy.gcd, "lcm": sympy.lcm, "isprime": sympy.isprime,
    "prime": sympy.prime, "primerange": lambda a, b: list(sympy.primerange(a, b)),
    "factorint": _factorint, "binomial": sympy.binomial,
    "mod": sympy.Mod, "Mod": sympy.Mod,
    # linear algebra
    "Matrix": _matrix, "matrix": _matrix,
    "det": lambda rows: _matrix(rows).det(),
    "inv": lambda rows: _matrix(rows).inv(),
    "transpose": lambda rows: _matrix(rows).T,
    "rank": lambda rows: _matrix(rows).rank(),
    "eigenvals": lambda rows: ", ".join(
        f"{val} (multiplicity {mult})" if mult > 1 else str(val)
        for val, mult in sorted(_matrix(rows).eigenvals().items(), key=str)
    ),
    # statistics
    "mean": _mean, "average": _mean, "median": _median, "stdev": _stdev,
    "variance": lambda v: _stdev(v) ** 2,
    "min": sympy.Min, "max": sympy.Max,
    # aggregates over literal lists
    "sum": lambda seq: sum(sympy.sympify(v) for v in seq),
}
_NAMESPACE.update(_SYMBOLS)


def _normalize(expression: str) -> str:
    """
    Rewrite common human/LLM notation into something sympy parses.

    Models frequently emit '×', '÷', '5!', '30% of 200' or a trailing '='.
    Rejecting those wastes a whole agent step, so translate them instead.
    """
    expr = expression.replace("×", "*").replace("÷", "/").replace("−", "-")
    expr = expr.replace("^", "**") if "**" not in expr else expr

    # "what is 2+2" / "calculate 2+2" / trailing "=" or "?"
    expr = re.sub(r"^\s*(?:what\s+is|calculate|compute|evaluate|solve\s+for\s+me)\s*[:,]?\s*",
                  "", expr, flags=re.IGNORECASE)
    expr = expr.strip().rstrip("=?").strip()

    # "30% of 200" -> "30/100*200";  bare "45%" -> "(45/100)"
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%\s+of\s+", r"(\1/100)*", expr, flags=re.IGNORECASE)
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", expr)

    # "5!" -> "factorial(5)"
    expr = re.sub(r"(\d+)\s*!", r"factorial(\1)", expr)

    return expr


def _format_result(result) -> str:
    """
    Render a sympy result exactly, adding a decimal form when it differs.

    ``22/7`` alone is unhelpful to a model writing prose; ``22/7 ≈ 3.142857``
    lets it answer either way without a second tool call.
    """
    if isinstance(result, dict):
        body = "\n".join(f"  {k} = {v}" for k, v in result.items())
        return f"Result:\n{body}"

    if isinstance(result, (list, tuple)):
        if not result:
            return "Result: no solutions"
        body = ", ".join(str(v) for v in result)
        return f"Result: {body}"

    if isinstance(result, str):
        return f"Result: {result}"

    # sympy signals division by zero as zoo/oo and 0/0 as nan; neither reads
    # as an answer, so name the condition instead.
    if result is sympy.zoo or result is sympy.nan:
        return ("Result: undefined — the expression divides by zero "
                "(no finite value exists).")

    exact = str(result)

    # Try a decimal rendering for anything numeric.
    try:
        numeric = sympy.N(result, 12)
        if numeric.is_number and not numeric.has(sympy.I):
            as_float = float(numeric)
            if as_float == int(as_float) and abs(as_float) < 1e15:
                return f"Result: {int(as_float)}"
            decimal = f"{as_float:.10g}"
            if decimal != exact:
                return f"Result: {exact}  ≈ {decimal}"
            return f"Result: {exact}"
    except (TypeError, ValueError, AttributeError):
        pass

    return f"Result: {exact}"


def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression with sympy.

    Args:
        expression: Any arithmetic, algebraic, calculus or matrix expression.

    Returns:
        A formatted result string, or an actionable error message.
    """
    raw = clean_input(expression, strip_fences=True)
    if not raw:
        return str(ToolError("No expression provided.",
                             "Pass something like '2 + 2' or 'solve(x**2-4, x)'."))

    expr = _normalize(raw)

    try:
        result = parse_expr(
            expr,
            transformations=TRANSFORMATIONS,
            local_dict=_NAMESPACE,
            evaluate=True,
        )
    except ToolError as exc:
        return str(exc)
    except (SyntaxError, TypeError, ValueError, AttributeError) as exc:
        return str(ToolError(
            f"Could not parse '{raw}': {exc}",
            "Use standard notation, e.g. '2*(3+4)', 'sqrt(16)', "
            "'solve(x**2-4, x)', 'diff(x**3, x)'.",
        ))
    except Exception as exc:  # sympy raises a wide variety of internal errors
        return str(ToolError(f"Could not evaluate '{raw}': {exc}"))

    try:
        return _format_result(result)
    except Exception as exc:
        return str(ToolError(f"Computed a result but could not format it: {exc}"))


calculator_tool = Tool(
    name="calculator",
    description=(
        "Evaluate math exactly: arithmetic and big integers, algebra "
        "(solve, factor, expand, simplify), calculus (diff, integrate, limit, "
        "Sum), linear algebra (det, inv, rank, eigenvals), number theory "
        "(isprime, factorint, gcd, binomial) and statistics (mean, median, "
        "stdev). Also understands '5!', '30% of 200' and '×/÷'. "
        "Input is a single expression, e.g. '2**100', 'solve(x**2-4, x)', "
        "'integrate(sin(x), x)', 'det([[1,2],[3,4]])'."
    ),
    function=calculator,
)
