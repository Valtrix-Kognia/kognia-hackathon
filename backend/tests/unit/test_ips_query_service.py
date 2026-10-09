import pytest

from app.application.services.ips_query_service import IpsQueryService
from app.application.services.value_catalog import ValueCatalog
from app.config.settings import Settings
from app.domain.errors import InvalidIdentifierError, UnknownFilterValueError
from app.domain.models.dataset_columns import Dimension, Metric
from app.domain.models.filter_request import FilterRequest
from tests.unit.fake_socrata_client import FakeSocrataClient


def build(responses=None) -> tuple[IpsQueryService, FakeSocrataClient]:
    fake = FakeSocrataClient(responses)
    catalog = ValueCatalog(fake, ttl_s=60)  # type: ignore[arg-type]
    return IpsQueryService(fake, catalog, Settings(_env_file=None)), fake  # type: ignore[arg-type]


async def test_count_returns_three_units_and_resolves_accents() -> None:
    service, fake = build([[{"registros": "469", "prestadores": "139", "sedes": "148"}]])
    result = await service.count(FilterRequest(departamento="quindio"))
    assert (result.registros, result.prestadores, result.sedes) == (469, 139, 148)
    assert result.metadata.filters == {"departamento": "Quindío"}
    assert "departamento = 'Quindío'" in fake.queries[0]
    assert any("no equivale a una IPS" in note for note in result.metadata.limitations)


async def test_ambiguous_municipio_includes_both_and_warns() -> None:
    service, fake = build([[{"registros": "3", "prestadores": "2", "sedes": "2"}]])
    result = await service.count(FilterRequest(municipio="armenia"))
    assert "municipio = 'ARMENIA'" in fake.queries[0]
    assert any("Antioquia, Quindío" in note for note in result.metadata.limitations)


async def test_municipio_scoped_to_departamento() -> None:
    service, fake = build([[{"registros": "1", "prestadores": "1", "sedes": "1"}]])
    result = await service.count(FilterRequest(departamento="Quindío", municipio="Armenia"))
    assert "departamento = 'Quindío' AND municipio = 'ARMENIA'" in fake.queries[0]
    assert not any("varias entidades" in note for note in result.metadata.limitations)


async def test_unknown_departamento_raises_with_suggestions() -> None:
    service, _ = build()
    with pytest.raises(UnknownFilterValueError) as exc:
        await service.count(FilterRequest(departamento="Quindioo xx"))
    assert exc.value.field == "departamento"


@pytest.mark.parametrize(
    ("raw", "expected"), [("públicas", "Pública"), ("privado", "Privada"), ("MIXTAS", "Mixta")]
)
async def test_naturaleza_variants(raw: str, expected: str) -> None:
    service, _ = build()
    filters, _ = await service.resolve_filters(FilterRequest(naturaleza=raw))
    assert filters.naturaleza == expected


async def test_nivel_words_and_missing_data_note() -> None:
    service, fake = build([[{"registros": "3", "prestadores": "3", "sedes": "3"}]])
    result = await service.count(FilterRequest(nivel_atencion="primer nivel"))
    assert "num_nivel_atencion = '1'" in fake.queries[0]
    assert any("60 %" in note for note in result.metadata.limitations)


async def test_nivel_sin_dato_uses_is_null() -> None:
    service, fake = build([[{"registros": "6", "prestadores": "6", "sedes": "6"}]])
    await service.count(FilterRequest(nivel_atencion="sin dato"))
    assert "num_nivel_atencion IS NULL" in fake.queries[0]


async def test_group_caps_top_n_and_labels_nulls() -> None:
    service, fake = build([[{"num_nivel_atencion": "1", "valor": "10"}, {"valor": "40"}]])
    result = await service.group(Dimension.NIVEL_ATENCION, Metric.SEDES, FilterRequest(), top_n=999)
    assert "LIMIT 40" in fake.queries[0]
    assert "count(DISTINCT c_digo_sede) AS valor" in fake.queries[0]
    assert [b.label for b in result.buckets] == ["1", "Sin dato"]


async def test_valle_warns_about_separate_districts() -> None:
    service, _ = build([[{"registros": "1", "prestadores": "1", "sedes": "1"}]])
    result = await service.count(FilterRequest(departamento="valle del cauca"))
    assert any("Cali" in note for note in result.metadata.limitations)


async def test_search_name_is_escaped_and_paginated() -> None:
    service, fake = build([[], [{"sedes": "0"}]])
    result = await service.search(FilterRequest(nombre="O'Higgins"), page=3, page_size=500)
    assert result.page_size == 25
    assert "LIKE '%O''HIGGINS%'" in fake.queries[0]
    assert result.total_sedes == 0
    assert result.items == []


async def test_details_rejects_non_numeric_id() -> None:
    service, _ = build()
    with pytest.raises(InvalidIdentifierError):
        await service.details("12 OR 1=1")


async def test_details_returns_none_when_empty() -> None:
    service, _ = build([[]])
    assert await service.details("123") is None
