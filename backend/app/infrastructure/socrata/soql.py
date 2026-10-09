import re
from dataclasses import dataclass, field

from app.domain.models.dataset_columns import Column

_ALIAS_PATTERN = re.compile(r"^[a-z_][a-z0-9_]{0,30}$")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_DIGITS = re.compile(r"^\d{1,15}$")


def quote_literal(value: str) -> str:
    """Escape a SoQL text literal: single quotes are doubled, control chars removed."""
    cleaned = _CONTROL_CHARS.sub(" ", value)
    return "'" + cleaned.replace("'", "''") + "'"


def numeric_literal(value: str) -> str:
    if not _DIGITS.match(value):
        raise ValueError("Identificador numérico inválido")
    return value


def like_contains(value: str) -> str:
    escaped = value.replace("%", "").replace("_", " ").strip()
    return quote_literal(f"%{escaped.upper()}%")


@dataclass(frozen=True)
class Projection:
    expression: str
    alias: str

    def render(self) -> str:
        if not _ALIAS_PATTERN.match(self.alias):
            raise ValueError(f"Alias inválido: {self.alias}")
        return f"{self.expression} AS {self.alias}"


@dataclass
class SoqlQuery:
    """SoQL statement restricted to whitelisted columns and escaped literals."""

    projections: list[Projection | Column] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    group_by: list[Column] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None
    distinct: bool = False

    def where_equals(self, column: Column, value: str) -> "SoqlQuery":
        self.conditions.append(f"{Column(column)} = {quote_literal(value)}")
        return self

    def where_in(
        self, column: Column, values: tuple[str, ...] | list[str]
    ) -> "SoqlQuery":
        if not values:
            raise ValueError("where_in requiere al menos un valor")
        if len(values) == 1:
            return self.where_equals(column, values[0])
        rendered = ", ".join(quote_literal(v) for v in values)
        self.conditions.append(f"{Column(column)} IN ({rendered})")
        return self

    def where_null(self, column: Column) -> "SoqlQuery":
        self.conditions.append(f"{Column(column)} IS NULL")
        return self

    def where_number(self, column: Column, value: str) -> "SoqlQuery":
        self.conditions.append(f"{Column(column)} = {numeric_literal(value)}")
        return self

    def where_contains_any(self, columns: list[Column], term: str) -> "SoqlQuery":
        pattern = like_contains(term)
        parts = [f"upper({Column(column)}) LIKE {pattern}" for column in columns]
        self.conditions.append("(" + " OR ".join(parts) + ")")
        return self

    def render(self) -> str:
        if not self.projections:
            raise ValueError("La consulta requiere columnas")
        select_items = [
            p.render() if isinstance(p, Projection) else str(Column(p))
            for p in self.projections
        ]
        sql = (
            "SELECT " + ("DISTINCT " if self.distinct else "") + ", ".join(select_items)
        )
        if self.conditions:
            sql += " WHERE " + " AND ".join(self.conditions)
        if self.group_by:
            sql += " GROUP BY " + ", ".join(str(Column(c)) for c in self.group_by)
        if self.order_by:
            sql += " ORDER BY " + ", ".join(self.order_by)
        if self.limit is not None:
            sql += f" LIMIT {int(self.limit)}"
        return sql
