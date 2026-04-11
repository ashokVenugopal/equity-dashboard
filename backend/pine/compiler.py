"""
Pine Script Compiler.

Compiles an AST into an ordered execution plan (list of operations on named Series).
Validates that all referenced builtins exist and variable dependencies are resolved.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .parser import (
    Assignment, BinaryOp, FunctionCall, Identifier,
    NumberLiteral, TernaryOp, UnaryMinus,
)


BUILTINS = {
    "sma": {"args": ["source", "length"], "description": "Simple Moving Average"},
    "ema": {"args": ["source", "length"], "description": "Exponential Moving Average"},
    "rsi": {"args": ["source", "length"], "description": "Relative Strength Index"},
    "cross": {"args": ["a", "b"], "description": "True when a crosses b (either direction)"},
    "crossover": {"args": ["a", "b"], "description": "True when a crosses above b"},
    "crossunder": {"args": ["a", "b"], "description": "True when a crosses below b"},
    "highest": {"args": ["source", "length"], "description": "Highest value over N bars"},
    "lowest": {"args": ["source", "length"], "description": "Lowest value over N bars"},
    "abs": {"args": ["value"], "description": "Absolute value"},
    "max": {"args": ["a", "b"], "description": "Maximum of two values"},
    "min": {"args": ["a", "b"], "description": "Minimum of two values"},
}

# Built-in series available without declaration
BUILTIN_SERIES = {"open", "high", "low", "close", "volume"}


@dataclass
class Op:
    """A single operation in the execution plan."""
    target: str            # Variable name to store result
    op_type: str           # "builtin", "binary", "ternary", "unary_minus", "literal", "alias"
    func: str = ""         # Function name for builtins
    args: list = field(default_factory=list)  # Argument references (variable names or literals)
    literal_value: float = 0.0


def compile_ast(statements: List[Assignment]) -> List[Op]:
    """Compile AST statements into an execution plan."""
    ops: List[Op] = []
    defined: set = set(BUILTIN_SERIES)
    temp_counter = [0]

    def temp_name() -> str:
        temp_counter[0] += 1
        return f"_t{temp_counter[0]}"

    def compile_expr(node, target: str = None) -> str:
        """Compile an expression node, returning the variable name holding the result."""
        name = target or temp_name()

        if isinstance(node, NumberLiteral):
            ops.append(Op(target=name, op_type="literal", literal_value=node.value))
            defined.add(name)
            return name

        if isinstance(node, Identifier):
            if node.name not in defined:
                raise NameError(f"Undefined variable: '{node.name}'")
            if target and target != node.name:
                ops.append(Op(target=name, op_type="alias", args=[node.name]))
                defined.add(name)
                return name
            return node.name

        if isinstance(node, FunctionCall):
            if node.name not in BUILTINS:
                raise NameError(f"Unknown function: '{node.name}'")
            expected_args = len(BUILTINS[node.name]["args"])
            if len(node.args) != expected_args:
                raise TypeError(
                    f"{node.name}() expects {expected_args} args, got {len(node.args)}"
                )
            arg_names = [compile_expr(a) for a in node.args]
            ops.append(Op(target=name, op_type="builtin", func=node.name, args=arg_names))
            defined.add(name)
            return name

        if isinstance(node, BinaryOp):
            left = compile_expr(node.left)
            right = compile_expr(node.right)
            ops.append(Op(target=name, op_type="binary", func=node.op, args=[left, right]))
            defined.add(name)
            return name

        if isinstance(node, TernaryOp):
            cond = compile_expr(node.condition)
            true_val = compile_expr(node.true_expr)
            false_val = compile_expr(node.false_expr)
            ops.append(Op(target=name, op_type="ternary", args=[cond, true_val, false_val]))
            defined.add(name)
            return name

        if isinstance(node, UnaryMinus):
            operand = compile_expr(node.operand)
            ops.append(Op(target=name, op_type="unary_minus", args=[operand]))
            defined.add(name)
            return name

        raise TypeError(f"Unknown AST node type: {type(node).__name__}")

    for stmt in statements:
        compile_expr(stmt.expr, target=stmt.name)
        defined.add(stmt.name)

    return ops
