import asyncio
from datetime import UTC, datetime
from typing import Any

from app.application.services.value_catalog import NIVEL_SIN_DATO, ValueCatalog
from app.config.settings import Settings
from app.domain.errors import InvalidIdentifierError
from app.domain.models.dataset_columns import (
    METRIC_DESCRIPTIONS,
    METRIC_EXPRESSIONS,
    Column,
    Dimension,
    Metric,
)
from app.domain.models.filter_request import FilterRequest
from app.domain.models.ips_filters import IpsFilters
from app.domain.models.query_results import (
    CapacityLine,
    CountResult,
    DatasetOverview,
    GroupBucket,
    GroupResult,
    IpsDetail,
    IpsSite,
    QueryMetadata,
    SearchResult,
)
from app.infrastructure.socrata.socrata_client import SocrataClient
from app.infrastructure.socrata.soql import Projection, SoqlQuery

MAX_TOP_N = 40
MAX_SEARCH_PAGE_SIZE = 25

ROW_UNIT_NOTE = (
    "Cada fila del dataset es una línea de capacidad instalada de una sede; "
    "una fila no equivale a una IPS."
)
SEPARATE_DISTRICTS = {
    "Barranquilla": "Atlántico",
    "Cartagena": "Bolívar",
    "Santa Marta": "Magdalena",
    "Cali": "Valle del cauca",
    "Buenaventura": "Valle del cauca",
}

_SITE_COLUMNS = [
    Column.CODIGO_SEDE,
    Column.NOMBRE_SEDE,
    Column.CODIGO_PRESTADOR,
    Column.NOMBRE_PRESTADOR,
    Column.DEPARTAMENTO,
    Column.MUNICIPIO,
    Column.NATURALEZA,
    Column.NIVEL_ATENCION,
    Column.DIRECCION,
    Column.TELEFONO,
]


class IpsQueryService:
    """Domain queries over dataset s2ru-bqt6. All SoQL is built from whitelisted parts."""

    def __init__(self, client: SocrataClient, catalog: ValueCatalog, settings: Settings) -> None:
        self._client = client
        self._catalog = catalog
        self._settings = settings

    async def resolve_filters(self, request: FilterRequest) -> tuple[IpsFilters, list[str]]:
        notes: list[str] = []
        departamento = (
            await self._catalog.resolve_departamento(request.departamento)
            if request.departamento
            else None
        )
        municipios: tuple[str, ...] = ()
        if request.municipio:
            names, deps = await self._catalog.resolve_municipio(request.municipio, departamento)
            municipios = tuple(names)
            if not departamento and len(deps) > 1:
                notes.append(
                    f"El municipio {names[0]} existe en varias entidades territoriales "
                    f"({', '.join(deps)}); el resultado las incluye todas."
                )
        if departamento in SEPARATE_DISTRICTS.values():
            districts = [d for d, parent in SEPARATE_DISTRICTS.items() if parent == departamento]
            notes.append(
                f"En esta fuente {', '.join(districts)} se reportan como entidad territorial "
                f"separada, por lo que no están incluidos en {departamento}."
            )
        filters = IpsFilters(
            departamento=departamento,
            municipios=municipios,
            naturaleza=(
                await self._catalog.resolve_naturaleza(request.naturaleza)
                if request.naturaleza
                else None
            ),
            nivel_atencion=(
                await self._catalog.resolve_nivel(request.nivel_atencion)
                if request.nivel_atencion
                else None
            ),
            grupo_capacidad=(
                await self._catalog.resolve_grupo(request.grupo_capacidad)
                if request.grupo_capacidad
                else None
            ),
            nombre=request.nombre or None,
        )
        if filters.nivel_atencion or request.nivel_atencion:
            notes.append(await self._nivel_note())
        return filters, notes

    async def count(self, request: FilterRequest) -> CountResult:
        filters, notes = await self.resolve_filters(request)
        query = SoqlQuery(
            projections=[
                Projection(METRIC_EXPRESSIONS[Metric.REGISTROS], "registros"),
                Projection(METRIC_EXPRESSIONS[Metric.PRESTADORES], "prestadores"),
                Projection(METRIC_EXPRESSIONS[Metric.SEDES], "sedes"),
            ]
        )
        self._apply_filters(query, filters)
        rows = await self._client.query(query.render(), page_size=1)
        row = rows[0] if rows else {}
        return CountResult(
            registros=_to_int(row.get("registros")),
            prestadores=_to_int(row.get("prestadores")),
            sedes=_to_int(row.get("sedes")),
            metadata=self._metadata(filters, [ROW_UNIT_NOTE, *notes]),
        )

    async def group(
        self,
        dimension: Dimension,
        metric: Metric,
        request: FilterRequest,
        top_n: int = 10,
        ascending: bool = False,
    ) -> GroupResult:
        top_n = max(1, min(top_n, MAX_TOP_N))
        filters, notes = await self.resolve_filters(request)
        column = Column(dimension.value)
        query = SoqlQuery(
            projections=[column, Projection(METRIC_EXPRESSIONS[metric], "valor")],
            group_by=[column],
            order_by=[f"valor {'ASC' if ascending else 'DESC'}", str(column)],
            limit=top_n,
        )
        self._apply_filters(query, filters)
        rows = await self._client.query(query.render(), page_size=top_n)
        buckets = [
            GroupBucket(label=row.get(column) or "Sin dato", value=_to_float(row.get("valor")))
            for row in rows
        ]
        if dimension is Dimension.NIVEL_ATENCION and not filters.nivel_atencion:
            notes.append(await self._nivel_note())
        if dimension is Dimension.DEPARTAMENTO:
            notes.append(
                "La columna departamento incluye distritos reportados por separado "
                "(Barranquilla, Cartagena, Santa Marta, Cali y Buenaventura)."
            )
        return GroupResult(
            dimension=dimension.value,
            metric=metric,
            metric_description=METRIC_DESCRIPTIONS[metric],
            buckets=buckets,
            metadata=self._metadata(filters, [ROW_UNIT_NOTE, *notes]),
        )

    async def search(
        self, request: FilterRequest, page: int = 1, page_size: int = 10
    ) -> SearchResult:
        page_size = max(1, min(page_size, MAX_SEARCH_PAGE_SIZE))
        page = max(1, min(page, 200))
        filters, notes = await self.resolve_filters(request)
        items_query = SoqlQuery(
            projections=list(_SITE_COLUMNS),
            group_by=list(_SITE_COLUMNS),
            order_by=[str(Column.NOMBRE_PRESTADOR), str(Column.NOMBRE_SEDE)],
        )
        total_query = SoqlQuery(
            projections=[Projection(METRIC_EXPRESSIONS[Metric.SEDES], "sedes")]
        )
        self._apply_filters(items_query, filters)
        self._apply_filters(total_query, filters)
        rows, total_rows = await asyncio.gather(
            self._client.query(items_query.render(), page_number=page, page_size=page_size),
            self._client.query(total_query.render(), page_size=1),
        )
        total = _to_int(total_rows[0].get("sedes")) if total_rows else 0
        return SearchResult(
            total_sedes=total,
            page=page,
            page_size=page_size,
            items=[_to_site(row) for row in rows],
            metadata=self._metadata(filters, notes),
        )

    async def details(self, codigo_sede: str) -> IpsDetail | None:
        codigo = codigo_sede.strip()
        if not codigo.isdigit() or len(codigo) > 15:
            raise InvalidIdentifierError("El código de sede debe ser numérico.")
        query = SoqlQuery(
            projections=[
                *_SITE_COLUMNS,
                Column.GRUPO_CAPACIDAD,
                Column.DESCRIPCION_CAPACIDAD,
                Column.CANTIDAD_CAPACIDAD,
                Column.FECHA_CORTE,
            ],
            order_by=[str(Column.GRUPO_CAPACIDAD), str(Column.DESCRIPCION_CAPACIDAD)],
        ).where_number(Column.CODIGO_SEDE, codigo)
        rows = await self._client.query(query.render(), page_size=500)
        if not rows:
            return None
        return IpsDetail(
            site=_to_site(rows[0]),
            capacidades=[
                CapacityLine(
                    grupo=row.get(Column.GRUPO_CAPACIDAD) or "Sin dato",
                    descripcion=row.get(Column.DESCRIPCION_CAPACIDAD) or "Sin dato",
                    cantidad=_to_float(row.get(Column.CANTIDAD_CAPACIDAD)),
                )
                for row in rows
            ],
            fecha_corte=rows[0].get(Column.FECHA_CORTE),
            metadata=self._metadata(IpsFilters(), [ROW_UNIT_NOTE]),
        )

    async def overview(self) -> DatasetOverview:
        metadata, totals, snapshot = await asyncio.gather(
            self._client.metadata(),
            self.count(FilterRequest()),
            self._catalog.snapshot(),
        )
        updated = metadata.get("rowsUpdatedAt")
        return DatasetOverview(
            name=str(metadata.get("name", "")),
            description=str(metadata.get("description", "")).split("\n")[0],
            attribution=metadata.get("attribution"),
            rows_updated_at=datetime.fromtimestamp(updated, UTC) if isinstance(updated, int) else None,
            totals=totals,
            fields={
                "departamento / municipio": "Ubicación de la sede (algunos distritos aparecen como departamento)",
                "nombre_prestador / c_digo_prestador": "Prestador inscrito en REPS",
                "nom_sede_ips / c_digo_sede": "Sede del prestador",
                "naturaleza": f"Naturaleza jurídica: {', '.join(snapshot.naturalezas)}",
                "num_nivel_atencion": "Nivel de atención (1, 2, 3); vacío en muchos registros",
                "nom_grupo_capacidad": f"Grupo de capacidad: {', '.join(snapshot.grupos)}",
                "num_cantidad_capacidad_instalada": "Cantidad instalada de esa capacidad",
            },
            limitations=[
                ROW_UNIT_NOTE,
                await self._nivel_note(),
                f"Corte de los datos: {snapshot.fecha_corte or 'no informado'}.",
                "No incluye servicios habilitados, especialidades, horarios, tarifas, "
                "calidad, ocupación ni EPS con convenio.",
            ],
        )

    async def _nivel_note(self) -> str:
        snapshot = await self._catalog.snapshot()
        return (
            f"El nivel de atención no está informado en el "
            f"{round(snapshot.nivel_missing_ratio * 100)} % de los registros."
        )

    @staticmethod
    def _apply_filters(query: SoqlQuery, filters: IpsFilters) -> None:
        if filters.departamento:
            query.where_equals(Column.DEPARTAMENTO, filters.departamento)
        if filters.municipios:
            query.where_in(Column.MUNICIPIO, filters.municipios)
        if filters.naturaleza:
            query.where_equals(Column.NATURALEZA, filters.naturaleza)
        if filters.nivel_atencion == NIVEL_SIN_DATO:
            query.where_null(Column.NIVEL_ATENCION)
        elif filters.nivel_atencion:
            query.where_equals(Column.NIVEL_ATENCION, filters.nivel_atencion)
        if filters.grupo_capacidad:
            query.where_equals(Column.GRUPO_CAPACIDAD, filters.grupo_capacidad)
        if filters.nombre:
            query.where_contains_any([Column.NOMBRE_PRESTADOR, Column.NOMBRE_SEDE], filters.nombre)

    def _metadata(self, filters: IpsFilters, limitations: list[str]) -> QueryMetadata:
        return QueryMetadata(
            dataset_id=self._settings.socrata_dataset_id,
            source=self._settings.socrata_query_url,
            queried_at=datetime.now(UTC),
            filters=filters.describe(),
            limitations=list(dict.fromkeys(limitations)),
        )


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_site(row: dict[str, Any]) -> IpsSite:
    return IpsSite(
        codigo_sede=str(row.get(Column.CODIGO_SEDE, "")),
        nombre_sede=row.get(Column.NOMBRE_SEDE) or "",
        codigo_prestador=str(row.get(Column.CODIGO_PRESTADOR, "")),
        nombre_prestador=row.get(Column.NOMBRE_PRESTADOR) or "",
        departamento=row.get(Column.DEPARTAMENTO) or "",
        municipio=row.get(Column.MUNICIPIO) or "",
        naturaleza=row.get(Column.NATURALEZA),
        nivel_atencion=row.get(Column.NIVEL_ATENCION),
        direccion=row.get(Column.DIRECCION),
        telefono=row.get(Column.TELEFONO),
    )
