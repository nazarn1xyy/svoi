"""Reads the DB schema out of docs/tech.md section 5 so tests compare models to the core."""

import ast
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

TECH_MD = Path(__file__).resolve().parents[3] / "docs/tech.md"


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    type_name: str  # SQLAlchemy type class, e.g. "BigInteger"; "" when inferred from Mapped[int]
    type_arg: str | None  # String length or enum class
    nullable: bool
    primary_key: bool
    unique: bool
    foreign_key: str | None
    ondelete: str | None
    default: str | None  # ast source of the Python-side default
    server_default: bool


@dataclass(frozen=True)
class TableSpec:
    name: str
    model: str
    columns: dict[str, ColumnSpec]
    indexes: dict[str, tuple[tuple[str, ...], str | None]] = field(default_factory=dict)
    uniques: set[tuple[str, ...]] = field(default_factory=set)
    checks: set[str] = field(default_factory=set)


def _block() -> str:
    text = TECH_MD.read_text()
    section = text[text.index("## 5. Схема БД") : text.index("## 6. ")]
    match = re.search(r"```python\n(.*?)```", section, re.DOTALL)
    assert match is not None
    return match.group(1)


def _kw(call: ast.Call, name: str) -> ast.expr | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _column(name: str, annotation: ast.expr, call: ast.Call) -> ColumnSpec:
    type_name, type_arg, fk, ondelete = "", None, None, None
    for arg in call.args:
        callee = arg.func if isinstance(arg, ast.Call) else arg
        callee_name = ast.unparse(callee)
        if callee_name == "ForeignKey" and isinstance(arg, ast.Call):
            fk = ast.literal_eval(arg.args[0])
            ondelete_node = _kw(arg, "ondelete")
            ondelete = ast.literal_eval(ondelete_node) if ondelete_node else None
        else:
            type_name = callee_name
            if isinstance(arg, ast.Call) and arg.args:
                type_arg = ast.unparse(arg.args[0])
    default = _kw(call, "default")
    primary_key = _kw(call, "primary_key")
    unique = _kw(call, "unique")
    return ColumnSpec(
        name=name,
        type_name=type_name,
        type_arg=type_arg,
        nullable="None" in ast.unparse(annotation),
        primary_key=bool(primary_key and ast.literal_eval(primary_key)),
        unique=bool(unique and ast.literal_eval(unique)),
        foreign_key=fk,
        ondelete=ondelete,
        default=ast.unparse(default) if default else None,
        server_default=_kw(call, "server_default") is not None,
    )


@cache
def tables() -> dict[str, TableSpec]:
    result: dict[str, TableSpec] = {}
    for node in ast.parse(_block()).body:
        if not isinstance(node, ast.ClassDef) or node.name == "Base":
            continue
        tablename = ""
        columns: dict[str, ColumnSpec] = {}
        table = TableSpec("", node.name, columns)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.targets[0], ast.Name):
                target = stmt.targets[0].id
                if target == "__tablename__":
                    tablename = ast.literal_eval(stmt.value)
                elif target == "__table_args__":
                    _table_args(stmt.value, table)
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and isinstance(stmt.value, ast.Call)
            ):
                columns[stmt.target.id] = _column(stmt.target.id, stmt.annotation, stmt.value)
        result[tablename] = TableSpec(
            tablename, node.name, columns, table.indexes, table.uniques, table.checks
        )
    return result


def _table_args(value: ast.expr, table: TableSpec) -> None:
    assert isinstance(value, ast.Tuple)
    for item in value.elts:
        assert isinstance(item, ast.Call)
        kind = ast.unparse(item.func)
        if kind == "Index":
            name, *cols = (ast.literal_eval(a) for a in item.args)
            using = _kw(item, "postgresql_using")
            table.indexes[name] = (tuple(cols), ast.literal_eval(using) if using else None)
        elif kind == "UniqueConstraint":
            table.uniques.add(tuple(ast.literal_eval(a) for a in item.args))
        elif kind == "CheckConstraint":
            name_node = _kw(item, "name")
            assert name_node is not None
            table.checks.add(ast.literal_eval(name_node))
