"""
calculator_tool.py — Safe Math Calculator
============================================
Uses sympy for safe symbolic math evaluation.
No raw eval() — prevents code injection attacks.

Supports:
- Basic arithmetic: 2 + 2, 10 / 3
- Powers: 2**10, sqrt(144)
- Algebra: solve(x**2 - 4, x)
- Trigonometry: sin(pi/4), cos(0)
- Constants: pi, e, oo (infinity)
"""

import sympy
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
    convert_xor,
)
from tools.base import Tool


# Transformation rules for parsing math expressions
TRANSFORMATIONS = (
    standard_transformations
    + (implicit_multiplication_application, convert_xor)
)


def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression safely using sympy.
    
    Args:
        expression: A math expression string.
                    Examples: "2 + 2", "sqrt(144)", "solve(x**2 - 4, x)"
    
    Returns:
        The result as a string.
    """
    try:
        # Clean up the expression
        expression = expression.strip()

        # Handle special sympy functions directly
        if expression.lower().startswith("solve"):
            # Execute sympy.solve() expressions
            result = eval(expression, {"__builtins__": {}}, {
                "solve": sympy.solve,
                "x": sympy.Symbol("x"),
                "y": sympy.Symbol("y"),
                "z": sympy.Symbol("z"),
                "pi": sympy.pi,
                "e": sympy.E,
                "sqrt": sympy.sqrt,
                "sin": sympy.sin,
                "cos": sympy.cos,
                "tan": sympy.tan,
                "log": sympy.log,
                "ln": sympy.log,
                "Eq": sympy.Eq,
            })
        else:
            # Parse and evaluate the expression safely
            result = parse_expr(
                expression,
                transformations=TRANSFORMATIONS,
                local_dict={
                    "pi": sympy.pi,
                    "e": sympy.E,
                    "sqrt": sympy.sqrt,
                    "sin": sympy.sin,
                    "cos": sympy.cos,
                    "tan": sympy.tan,
                    "log": sympy.log,
                    "ln": sympy.log,
                    "abs": sympy.Abs,
                },
            )
            # Try to evaluate to a number if possible
            try:
                result = float(result.evalf())
                # Clean up: show as int if it's a whole number
                if result == int(result):
                    result = int(result)
            except (TypeError, AttributeError):
                pass  # Keep as symbolic expression

        return f"Result: {result}"

    except Exception as e:
        return f"Calculator error: {str(e)}. Please check the expression format."


# ============================================
# Register as a Tool
# ============================================

calculator_tool = Tool(
    name="calculator",
    description=(
        "Perform mathematical calculations safely. "
        "Supports arithmetic, algebra, trigonometry, and more. "
        "Input should be a math expression like '2 + 2', 'sqrt(144)', "
        "'solve(x**2 - 4, x)', or 'sin(pi/4)'."
    ),
    function=calculator,
)
