"""Reads the contract out of docs/tech.md so tests compare code against the core, not itself."""

import ast
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

TECH_MD = Path(__file__).resolve().parents[3] / "docs/tech.md"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    annotation: str
    default: ast.expr | None


@dataclass(frozen=True)
class ClassSpec:
    name: str
    bases: tuple[str, ...]
    own_fields: tuple[FieldSpec, ...]
    topic: str | None


def text() -> str:
    return TECH_MD.read_text()


def _section(number: int) -> str:
    start = re.search(rf"^## {number}\. ", text(), re.MULTILINE)
    end = re.search(rf"^## {number + 1}\. ", text(), re.MULTILINE)
    assert start is not None
    assert end is not None
    return text()[start.start() : end.start()]


def _python_blocks(section: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", section, re.DOTALL)


def core_version() -> int:
    match = re.search(r"^\*\*Версія ядра: v(\d+)\*\*", text(), re.MULTILINE)
    assert match is not None
    return int(match.group(1))


@cache
def constants() -> dict[str, Any]:
    (block,) = _python_blocks(_section(4))
    namespace: dict[str, Any] = {}
    exec(compile(block, "tech.md#4", "exec"), namespace)  # noqa: S102 - trusted repo doc
    return {k: v for k, v in namespace.items() if k.isupper()}


@cache
def enums() -> dict[str, tuple[str, ...]]:
    block = _python_blocks(_section(6))[0]
    result: dict[str, tuple[str, ...]] = {}
    for raw in block.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            name, members = line.split("=", 1)
            result[name.strip()] = tuple(m.strip() for m in members.split("|"))
    return result


@cache
def classes() -> dict[str, ClassSpec]:
    result: dict[str, ClassSpec] = {}
    for number in (6, 7, 8):
        blocks = _python_blocks(_section(number))
        if number == 6:
            blocks = blocks[1:]  # the first block is the enum shorthand
        for block in blocks:
            for line_no, node in enumerate(ast.parse(block).body):
                if isinstance(node, ast.ClassDef) and node.name != "ErrorCode":
                    result[node.name] = _class_spec(node, block, line_no)
    return result


def _class_spec(node: ast.ClassDef, block: str, _: int) -> ClassSpec:
    fields = tuple(
        FieldSpec(stmt.target.id, ast.unparse(stmt.annotation), stmt.value)
        for stmt in node.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    )
    header = block.splitlines()[node.lineno - 1]
    topic = re.search(r'топік "([a-z_.]+)"', header)
    return ClassSpec(
        node.name,
        tuple(ast.unparse(base) for base in node.bases),
        fields,
        topic.group(1) if topic else None,
    )


def all_fields(name: str) -> tuple[FieldSpec, ...]:
    """Fields in pydantic order: inherited from spec bases first."""
    spec = classes()[name]
    inherited: tuple[FieldSpec, ...] = ()
    for base in spec.bases:
        if base in classes():
            inherited += all_fields(base)
    return inherited + spec.own_fields


@cache
def error_codes() -> tuple[str, ...]:
    block = _python_blocks(_section(6))[1]
    tree = ast.parse(block)
    (error_code,) = (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ErrorCode")
    return tuple(
        stmt.targets[0].id
        for stmt in error_code.body
        if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name)
    )


@cache
def aliases() -> dict[str, str]:
    result: dict[str, str] = {}
    for block in _python_blocks(_section(7)):
        for node in ast.parse(block).body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                result[node.targets[0].id] = ast.unparse(node.value)
    return result
