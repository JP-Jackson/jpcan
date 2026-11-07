"""Safe evaluator for profile formulas like '((A*256)+B)/4'.

Bytes are A, B, C, ... (A = first data byte after the echoed PID/DID).
No eval(): formulas are parsed to an AST and only whitelisted nodes run.
"""

from __future__ import annotations

import ast
import operator
import string
from typing import Callable, Sequence

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.LShift: operator.lshift, ast.RShift: operator.rshift,
    ast.BitAnd: operator.and_, ast.BitOr: operator.or_,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _signed8(x):
    x = int(x) & 0xFF
    return x - 0x100 if x & 0x80 else x


def _signed16(x):
    x = int(x) & 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


_FUNCS: dict[str, Callable] = {
    "min": min, "max": max, "abs": abs,
    "signed": _signed8, "signed8": _signed8, "signed16": _signed16,
}
_LETTERS = string.ascii_uppercase


class FormulaError(ValueError):
    pass


class Formula:
    """Bytes formula (A, B, ...) or, with `names`, an expression over PID keys."""

    def __init__(self, text: str, names: set[str] | None = None):
        self.text = text
        self.names = names
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise FormulaError(f"bad formula {text!r}: {e}") from None
        self._check(tree.body)
        self._tree = tree.body
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - set(_FUNCS)
        self.vars = used if names is not None else set()
        self.nbytes = 0 if names is not None else max(
            (_LETTERS.index(v) + 1 for v in used), default=0)

    def _check(self, node):
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            self._check(node.left)
            self._check(node.right)
        elif isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            self._check(node.operand)
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
            pass
        elif isinstance(node, ast.Name) and self._name_ok(node.id):
            pass
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in _FUNCS and not node.keywords):
            for a in node.args:
                self._check(a)
        else:
            raise FormulaError(f"disallowed element in {self.text!r}: {ast.dump(node)[:60]}")

    def _name_ok(self, name: str) -> bool:
        if self.names is not None:
            return name in self.names
        return name in _LETTERS and len(name) == 1

    def __call__(self, data) -> float:
        if self.names is not None:  # derived: mapping of PID key -> value
            missing = self.vars - set(data)
            if missing:
                raise FormulaError(f"{self.text!r} missing {sorted(missing)}")
            return self._eval(self._tree, data)
        if len(data) < self.nbytes:
            raise FormulaError(f"{self.text!r} needs {self.nbytes} bytes, got {len(data)}")
        env = dict(zip(_LETTERS, data))
        return self._eval(self._tree, env)

    def _eval(self, n, env):
        if isinstance(n, ast.BinOp):
            return _BIN[type(n.op)](self._eval(n.left, env), self._eval(n.right, env))
        if isinstance(n, ast.UnaryOp):
            return _UNARY[type(n.op)](self._eval(n.operand, env))
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return env[n.id]
        return _FUNCS[n.func.id](*(self._eval(a, env) for a in n.args))
