"""Hard project rule: every function in the app must have CC < 10.

This is the kind of constraint that has to be asserted, not remembered. The ruff config
already enforces ``max-complexity = 9``, but if someone disables that rule or adds code
that escapes it, this test is the safety net.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
APP = ROOT / "app"
THRESHOLD = 10


def _walk_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def test_all_functions_meet_complexity_budget() -> None:
    """Walk every Python file under app/ and assert CC for every function."""
    offenders: list[tuple[str, int, str]] = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ROOT)
        for func in _walk_functions(tree):
            complexity = _cyclomatic_complexity(func)
            if complexity >= THRESHOLD:
                offenders.append((f"{rel}:{func.lineno}", complexity, func.name))
    assert not offenders, (
        f"functions with CC >= {THRESHOLD}: {offenders}\n"
        f"Project rule: every function must stay under CC {THRESHOLD}. "
        f"Either break the function up, or use a dispatch table to reduce branches."
    )


def _cyclomatic_complexity(func: ast.AST) -> int:
    """Standard McCabe: 1 + the number of decision points."""
    points = 0
    for node in ast.walk(func):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.IfExp)):
            points += 1
        elif isinstance(node, ast.ExceptHandler):
            points += 1
        elif isinstance(node, ast.BoolOp):
            # ``a and b and c`` has two decision points, not one.
            points += max(0, len(node.values) - 1)
        elif isinstance(node, ast.Match):
            points += max(0, len(node.cases))
        elif isinstance(node, ast.Assert):
            points += 1
    return 1 + points
