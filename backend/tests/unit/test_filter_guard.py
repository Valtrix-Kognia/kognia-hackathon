import pytest

from app.domain.models.filter_request import FilterRequest
from app.voice.filter_guard import guard_filters


def test_unrequested_enum_filters_are_dropped() -> None:
    request = FilterRequest(
        departamento="Caldas", naturaleza="Pública", nivel_atencion="sin dato"
    )
    guarded, dropped = guard_filters(request, "Kognia, ¿cuántas IPS hay en Caldas?")
    assert guarded.departamento == "Caldas"
    assert guarded.naturaleza is None and guarded.nivel_atencion is None
    assert dropped == ["naturaleza=Pública", "nivel_atencion=sin dato"]


@pytest.mark.parametrize(
    ("text", "field", "value"),
    [
        ("¿cuántos prestadores públicos hay en Antioquia?", "naturaleza", "Pública"),
        ("cuántas sedes privadas hay", "naturaleza", "Privada"),
        ("IPS de primer nivel en Huila", "nivel_atencion", "1"),
        ("¿cuántas ambulancias hay en Nariño?", "grupo_capacidad", "ambulancias"),
        ("cuántas camas hay en Risaralda", "grupo_capacidad", "camas"),
    ],
)
def test_mentioned_filters_are_kept(text: str, field: str, value: str) -> None:
    guarded, dropped = guard_filters(FilterRequest(**{field: value}), text)
    assert getattr(guarded, field) == value
    assert dropped == []


def test_no_request_text_means_no_guard() -> None:
    request = FilterRequest(naturaleza="Mixta")
    assert guard_filters(request, "") == (request, [])
