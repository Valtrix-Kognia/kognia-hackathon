import pytest

from app.domain.models.dataset_columns import Column
from app.infrastructure.socrata.soql import Projection, SoqlQuery, like_contains, quote_literal


def test_quote_literal_doubles_single_quotes() -> None:
    assert quote_literal("O'Brien") == "'O''Brien'"


def test_quote_literal_strips_control_chars() -> None:
    assert quote_literal("a\nb\x00c") == "'a b c'"


def test_injection_attempt_stays_inside_literal() -> None:
    query = SoqlQuery(projections=[Column.DEPARTAMENTO]).where_equals(
        Column.DEPARTAMENTO, "x' OR '1'='1"
    )
    assert query.render() == "SELECT departamento WHERE departamento = 'x'' OR ''1''=''1'"


def test_like_contains_removes_wildcards_and_uppercases() -> None:
    assert like_contains("san%juan_") == "'%SANJUAN%'"


def test_unknown_column_is_rejected() -> None:
    query = SoqlQuery(projections=[Column.DEPARTAMENTO])
    query.group_by.append("gerente; DROP")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        query.render()


def test_invalid_alias_is_rejected() -> None:
    with pytest.raises(ValueError):
        Projection("count(*)", "n; DELETE").render()


def test_numeric_filter_requires_digits() -> None:
    with pytest.raises(ValueError):
        SoqlQuery(projections=[Column.CODIGO_SEDE]).where_number(Column.CODIGO_SEDE, "1 OR 1=1")


def test_full_group_query_renders() -> None:
    query = SoqlQuery(
        projections=[Column.DEPARTAMENTO, Projection("count(*)", "valor")],
        group_by=[Column.DEPARTAMENTO],
        order_by=["valor DESC"],
        limit=5,
    ).where_in(Column.NATURALEZA, ["Pública", "Mixta"])
    assert query.render() == (
        "SELECT departamento, count(*) AS valor WHERE naturaleza IN ('Pública', 'Mixta') "
        "GROUP BY departamento ORDER BY valor DESC LIMIT 5"
    )
