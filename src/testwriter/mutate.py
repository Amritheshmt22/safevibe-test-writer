"""Deterministic AST-based mutation engine.

Implements a standard set of mutation operators from the mutation-testing
literature, one mutation per mutant:

- AOR  Arithmetic Operator Replacement  (a + b  -> a - b, a * b -> a / b, ...)
- ROR  Relational Operator Replacement  (== -> !=, < -> <=, > -> >=, in -> not in, ...)
- LCR  Logical Connector Replacement    (and -> or, or -> and)
- UOI  Unary Operator Insertion/Deletion (not x -> x, -x -> x)
- CRP  Constant Replacement             (n -> n + 1, "s" -> "", True -> False)
- RVR  Return Value Replacement         (return x -> return None)

Mutants are generated deterministically (sorted by source position) so a
run can be reproduced exactly. The number of mutants per module is capped;
when the cap is hit an evenly spaced deterministic sample is taken.

The engine intentionally uses only the standard library so the whole
pipeline stays dependency-light and inspectable. An optional cross-check
against mutmut/cosmic-ray is future work (see docs/evaluation-hygiene.md).
"""
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass

MAX_MUTANTS_DEFAULT = 150

_AOR_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.Div,
    ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.Mult,
    ast.Pow: ast.Mult,
}
_ROR_SWAP = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}


@dataclass(frozen=True)
class MutationPoint:
    """A single place where one operator can be applied."""

    operator: str  # e.g. "AOR"
    node_type: str  # e.g. "BinOp"
    lineno: int
    col: int
    detail: str  # human description, e.g. "Add->Sub"


@dataclass
class Mutant:
    """One mutated variant of a module."""

    id: str
    operator: str
    lineno: int
    description: str
    source: str  # full mutated source code of the module


class _Collector(ast.NodeVisitor):
    """Finds every mutation point in a module's AST."""

    def __init__(self) -> None:
        self.points: list[MutationPoint] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        repl = _AOR_SWAP.get(type(node.op))
        if repl is not None:
            self.points.append(
                MutationPoint("AOR", "BinOp", node.lineno, node.col_offset,
                              f"{type(node.op).__name__}->{repl.__name__}"))
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if len(node.ops) == 1:
            repl = _ROR_SWAP.get(type(node.ops[0]))
            if repl is not None:
                self.points.append(
                    MutationPoint("ROR", "Compare", node.lineno, node.col_offset,
                                  f"{type(node.ops[0]).__name__}->{repl.__name__}"))
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        repl = ast.Or if isinstance(node.op, ast.And) else ast.And
        self.points.append(
            MutationPoint("LCR", "BoolOp", node.lineno, node.col_offset,
                          f"{type(node.op).__name__}->{repl.__name__}"))
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if isinstance(node.op, (ast.Not, ast.USub)):
            self.points.append(
                MutationPoint("UOI", "UnaryOp", node.lineno, node.col_offset,
                              f"remove {type(node.op).__name__}"))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        v = node.value
        if isinstance(v, bool):
            self.points.append(
                MutationPoint("CRP", "Constant", node.lineno, node.col_offset,
                              f"{v}->{not v}"))
        elif isinstance(v, int):
            self.points.append(
                MutationPoint("CRP", "Constant", node.lineno, node.col_offset,
                              f"{v}->{v + 1}"))
        elif isinstance(v, str) and v:
            self.points.append(
                MutationPoint("CRP", "Constant", node.lineno, node.col_offset,
                              f"{v!r}->''"))
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            self.points.append(
                MutationPoint("RVR", "Return", node.lineno, node.col_offset,
                              "return value -> None"))
        self.generic_visit(node)


class _Applier(ast.NodeTransformer):
    """Applies exactly one mutation point (matched by node position)."""

    def __init__(self, point: MutationPoint) -> None:
        self.point = point
        self.applied = False

    def _match(self, node: ast.AST, node_type: str) -> bool:
        return (not self.applied
                and type(node).__name__ == node_type
                and getattr(node, "lineno", None) == self.point.lineno
                and getattr(node, "col_offset", None) == self.point.col)

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "BinOp"):
            node.op = _AOR_SWAP[type(node.op)]()
            self.applied = True
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "Compare"):
            node.ops = [_ROR_SWAP[type(node.ops[0])]()]
            self.applied = True
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "BoolOp"):
            node.op = (ast.Or() if isinstance(node.op, ast.And) else ast.And())
            self.applied = True
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "UnaryOp"):
            self.applied = True
            return node.operand  # remove the unary operator
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "Constant"):
            v = node.value
            if isinstance(v, bool):
                node.value = not v
            elif isinstance(v, int):
                node.value = v + 1
            elif isinstance(v, str):
                node.value = ""
            self.applied = True
        return node

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        if self._match(node, "Return"):
            node.value = ast.Constant(value=None)
            self.applied = True
        return node


def collect_mutation_points(source: str) -> list[MutationPoint]:
    """Return all mutation points in *source*, in deterministic order."""
    tree = ast.parse(source)
    collector = _Collector()
    collector.visit(tree)
    collector.points.sort(key=lambda p: (p.lineno, p.col, p.operator, p.detail))
    return collector.points


def apply_mutation(source: str, point: MutationPoint) -> str:
    """Return *source* with exactly the mutation *point* applied."""
    tree = ast.parse(source)
    applier = _Applier(point)
    new_tree = applier.visit(tree)
    if not applier.applied:  # pragma: no cover - defensive
        raise ValueError(f"mutation point not applicable: {point}")
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def generate_mutants(source: str, max_mutants: int = MAX_MUTANTS_DEFAULT) -> list[Mutant]:
    """Generate mutants for a module, deterministically capped at *max_mutants*."""
    points = collect_mutation_points(source)
    if len(points) > max_mutants:
        step = len(points) / max_mutants
        points = [points[int(i * step)] for i in range(max_mutants)]
    mutants: list[Mutant] = []
    for point in points:
        try:
            mutated = apply_mutation(source, point)
        except (ValueError, SyntaxError):
            continue
        if mutated == source:  # defensive: mutation must change the code
            continue
        mid = hashlib.sha1(
            f"{point.operator}|{point.lineno}|{point.col}|{point.detail}".encode()
        ).hexdigest()[:10]
        mutants.append(Mutant(
            id=mid,
            operator=point.operator,
            lineno=point.lineno,
            description=point.detail,
            source=mutated,
        ))
    return mutants
