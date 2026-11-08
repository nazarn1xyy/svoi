"""Declarative base and enum column helper."""

from enum import StrEnum

from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for every table."""


def pg_enum(e: type[StrEnum]) -> Enum:
    """PostgreSQL ENUM named after the class, storing member values."""
    return Enum(e, name=e.__name__.lower(), values_callable=lambda x: [i.value for i in x])
