from app.application.services.text_matching import normalize
from app.domain.models.filter_request import FilterRequest

_MENTION_STEMS: dict[str, tuple[str, ...]] = {
    "naturaleza": ("PUBLIC", "PRIVAD", "MIXT", "NATURALEZA", "OFICIAL"),
    "nivel_atencion": ("NIVEL", "PRIMER", "SEGUND", "TERCER", "COMPLEJIDAD"),
    "grupo_capacidad": (
        "CAMA", "CAMILLA", "AMBULANCIA", "CONSULTORIO", "SALA", "SILLA", "UNIDAD",
        "MOVIL", "CAPACIDAD",
    ),
}  # fmt: skip


def guard_filters(
    request: FilterRequest, user_text: str
) -> tuple[FilterRequest, list[str]]:
    """Drop categorical filters the user never asked for.

    Measured in e2e runs: the LLM sometimes fills optional enum arguments (e.g.
    nivel_atencion="sin dato") or splits one question into one call per naturaleza,
    which silently changes the counted population. Location and name filters are kept;
    they are validated against the catalog anyway.
    """
    if not user_text.strip():
        return request, []
    tokens = normalize(user_text).split()
    dropped: list[str] = []
    updates: dict[str, None] = {}
    for field, stems in _MENTION_STEMS.items():
        if getattr(request, field) is None:
            continue
        if not any(token.startswith(stems) for token in tokens):
            dropped.append(f"{field}={getattr(request, field)}")
            updates[field] = None
    return (request.model_copy(update=updates) if updates else request), dropped
