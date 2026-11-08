"""K6 acceptance: db/models.py mirrors docs/tech.md section 5 table by table."""

from datetime import time
from typing import Any

import pytest
import schema_spec
from geoalchemy2 import Geography
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Index,
    String,
    Table,
    UniqueConstraint,
)
from svoi_api.db import models
from svoi_api.db.base import Base
from svoi_contracts import enums

TABLES = schema_spec.tables()


def _table(name: str) -> Table:
    return Base.metadata.tables[name]


def test_metadata_has_exactly_the_core_tables() -> None:
    assert set(Base.metadata.tables) == set(TABLES)


@pytest.mark.parametrize("name", sorted(TABLES))
def test_model_class_names_match(name: str) -> None:
    assert getattr(models, TABLES[name].model).__table__ is _table(name)


@pytest.mark.parametrize("name", sorted(TABLES))
def test_columns_match(name: str) -> None:
    table = _table(name)
    spec = TABLES[name]
    assert list(table.columns.keys()) == list(spec.columns)
    for col_spec in spec.columns.values():
        _check_column(table.columns[col_spec.name], col_spec)


def _check_column(col: Column[Any], spec: schema_spec.ColumnSpec) -> None:
    where = f"{col.table.name}.{col.name}"
    assert col.nullable == (spec.nullable and not spec.primary_key), where
    assert col.primary_key == spec.primary_key, where
    assert bool(col.unique) == spec.unique, where
    assert (col.server_default is not None) == spec.server_default, where
    _check_type(col, spec, where)
    _check_foreign_key(col, spec, where)
    _check_default(col, spec, where)


def _check_type(col: Column[Any], spec: schema_spec.ColumnSpec, where: str) -> None:
    if spec.type_name == "":
        # FK-only columns take the referenced column's type, so ids stay BIGINT end to end
        (fk,) = col.foreign_keys
        assert type(col.type) is type(fk.column.type), where
    elif spec.type_name == "pg_enum":
        assert isinstance(col.type, Enum), where
        assert col.type.enum_class is getattr(enums, str(spec.type_arg)), where
        assert col.type.name == str(spec.type_arg).lower(), where
    else:
        assert type(col.type).__name__ == spec.type_name, where
    if spec.type_name == "String":
        assert isinstance(col.type, String)
        assert col.type.length == int(str(spec.type_arg)), where
    if spec.type_name == "DateTime":
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True, where
    if spec.type_name == "Geography":
        assert isinstance(col.type, Geography)
        assert (col.type.geometry_type, col.type.srid) == ("POINT", 4326), where
        # tech.md declares GiST indexes explicitly; an implicit one would duplicate them
        assert col.type.spatial_index is False, where


def _check_foreign_key(col: Column[Any], spec: schema_spec.ColumnSpec, where: str) -> None:
    fks = list(col.foreign_keys)
    if spec.foreign_key is None:
        assert fks == [], where
        return
    (fk,) = fks
    assert fk.target_fullname == spec.foreign_key, where
    assert fk.ondelete == spec.ondelete, where


def _check_default(col: Column[Any], spec: schema_spec.ColumnSpec, where: str) -> None:
    if spec.default is None:
        assert col.default is None, where
        return
    namespace = {**vars(enums), "time": time}
    expected = eval(spec.default, namespace)  # noqa: S307 - expression from the repo's tech.md
    assert col.default is not None, where
    assert getattr(col.default, "arg", None) == expected, where


@pytest.mark.parametrize("name", sorted(TABLES))
def test_indexes_and_constraints_match(name: str) -> None:
    table = _table(name)
    spec = TABLES[name]
    indexes = {
        i.name: (tuple(c.name for c in i.columns), i.dialect_options["postgresql"]["using"])
        for i in table.indexes
        if isinstance(i, Index)
    }
    assert indexes == spec.indexes
    uniques = {
        tuple(c.name for c in con.columns)
        for con in table.constraints
        if isinstance(con, UniqueConstraint)
    }
    assert uniques == spec.uniques
    checks = {str(con.name) for con in table.constraints if isinstance(con, CheckConstraint)}
    assert checks == spec.checks
