"""Builtin tool sandbox (spec §9.3, M4).

Every tool declares its `ToolSpec` first: side effect, scopes, timeout, egress.
The executor refuses anything the registry does not describe. The builtins are
deliberately small — no shell, no network, no writes — so that the gatekeeper
has something real to guard while the runtime proves its loop.

Tools receive a JSON-ish `args` dict and return a dict observation payload.
"""

from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from par.schemas.core import ToolSpec

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]

MAX_TEXT_CHARS = 4000


class ToolError(Exception):
    """Tool refused or failed; the executor turns it into a failed result."""


class ToolBox:
    """`name -> (spec, handler)` registry shared by planner and executor."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        if spec.name in self._specs:
            raise ValueError(f"tool already registered: {spec.name}")
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    @property
    def specs(self) -> dict[str, ToolSpec]:
        return dict(self._specs)

    def handler(self, name: str) -> ToolHandler:
        try:
            return self._handlers[name]
        except KeyError as exc:  # pragma: no cover - guarded by the gatekeeper
            raise ToolError(f"unknown_tool:{name}") from exc

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "version": s.version,
                "side_effect": s.side_effect,
                "timeout_default_s": s.timeout_default_s,
                "requires_approval": s.requires_approval,
                "input_schema": s.input_schema,
            }
            for s in self._specs.values()
        ]


# --------------------------------------------------------------------------- #
# builtin handlers
# --------------------------------------------------------------------------- #

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_MAX_EXPONENT = 64


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ToolError("exponent_too_large")
        return _BIN_OPS[type(node.op)](left, right)
    raise ToolError("unsupported_expression")


def calc_eval(args: dict[str, Any]) -> dict[str, Any]:
    expression = str(args.get("expression") or "").strip()
    if not expression:
        raise ToolError("empty_expression")
    if len(expression) > 200:
        raise ToolError("expression_too_long")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ToolError(f"syntax_error:{exc.msg}") from exc
    value = _eval_node(tree)
    if value != value or value in (float("inf"), float("-inf")):
        raise ToolError("non_finite_result")
    return {"expression": expression, "value": value}


def time_now(args: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "weekday": now.strftime("%A"),
        "tz": now.tzname() or "local",
    }


class FileSandbox:
    """Read-only view of one workspace directory, no symlink escape."""

    def __init__(self, root: Path, max_bytes: int = 64 * 1024) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def read(self, args: dict[str, Any]) -> dict[str, Any]:
        raw = str(args.get("path") or "").strip()
        if not raw:
            raise ToolError("empty_path")
        target = (self.root / raw).resolve()
        if target != self.root and self.root not in target.parents:
            raise ToolError("path_outside_workspace")
        if not target.is_file():
            raise ToolError("not_a_file")
        size = target.stat().st_size
        if size > self.max_bytes:
            raise ToolError(f"file_too_large:{size}>{self.max_bytes}")
        text = target.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > MAX_TEXT_CHARS
        return {
            "path": str(target.relative_to(self.root)).replace("\\", "/"),
            "bytes": size,
            "text": text[:MAX_TEXT_CHARS],
            "truncated": truncated,
        }


def build_toolbox(workspace: Path, max_file_bytes: int = 64 * 1024) -> ToolBox:
    box = ToolBox()
    box.register(
        ToolSpec(
            name="time.now",
            side_effect="none",
            input_schema={"tz": "string?"},
            timeout_default_s=2.0,
        ),
        time_now,
    )
    box.register(
        ToolSpec(
            name="calc.eval",
            side_effect="none",
            input_schema={"expression": "string"},
            timeout_default_s=2.0,
        ),
        calc_eval,
    )
    sandbox = FileSandbox(workspace, max_bytes=max_file_bytes)
    box.register(
        ToolSpec(
            name="fs.read",
            side_effect="read",
            scopes=["workspace:read"],
            input_schema={"path": "string"},
            timeout_default_s=10.0,
        ),
        sandbox.read,
    )
    return box
