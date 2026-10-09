import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from livekit.agents import RunContext, llm
from livekit.agents.llm import ToolError, function_tool
from pydantic import BaseModel

from app.application.services.ips_query_service import ROW_UNIT_NOTE, IpsQueryService
from app.domain.errors import DomainError
from app.domain.models.dataset_columns import Dimension, Metric
from app.domain.models.filter_request import FilterRequest
from app.infrastructure.socrata.errors import SocrataError
from app.infrastructure.socrata.socrata_client import http_durations_ms
from app.voice.event_publisher import EventPublisher
from app.voice.filter_guard import guard_filters
from app.voice.latency_metrics import LatencyMetricsService, ToolTiming

logger = logging.getLogger("kognia.tools")

DimensionName = Literal[
    "departamento",
    "municipio",
    "naturaleza",
    "nivel_atencion",
    "grupo_capacidad",
    "descripcion_capacidad",
]
MetricName = Literal["prestadores", "sedes", "registros", "capacidad_instalada"]

FILLER_PHRASES = (
    "Un momento, consulto los datos oficiales.",
    "Déjame revisar la fuente oficial.",
    "Ya lo consulto en los datos oficiales.",
)

_DIMENSIONS: dict[str, Dimension] = {
    "departamento": Dimension.DEPARTAMENTO,
    "municipio": Dimension.MUNICIPIO,
    "naturaleza": Dimension.NATURALEZA,
    "nivel_atencion": Dimension.NIVEL_ATENCION,
    "grupo_capacidad": Dimension.GRUPO_CAPACIDAD,
    "descripcion_capacidad": Dimension.DESCRIPCION_CAPACIDAD,
}


def spoken_limitations(limitations: list[str]) -> list[str]:
    """Notes the LLM should consider saying. The row-unit and data-snapshot notes stay in
    the dashboard only: repeating them made every answer 8-12 s long (e2e traces)."""
    return [
        note
        for note in limitations
        if note != ROW_UNIT_NOTE and "agregados descargados" not in note
    ]


class IpsToolset(llm.Toolset):
    """LLM-facing tools. The LLM only chooses typed parameters; SoQL is built server-side."""

    def __init__(
        self,
        service: IpsQueryService,
        events: EventPublisher,
        latency: LatencyMetricsService | None = None,
        filler_delay_s: float | None = 0.7,
        request_text: Callable[[], str] = lambda: "",
    ) -> None:
        super().__init__(id="ips_tools")
        self._service = service
        self._events = events
        self._latency = latency
        self._filler_count = 0
        self._filler_delay_s = filler_delay_s
        self._request_text = request_text
        self._dropped: list[str] = []

    def _guard(self, request: FilterRequest) -> FilterRequest:
        guarded, self._dropped = guard_filters(request, self._request_text())
        if self._dropped:
            logger.info("dropping filters not mentioned by the user: %s", self._dropped)
        return guarded

    def _filler(self, step: int) -> str | None:
        if step > 0:
            return None
        phrase = FILLER_PHRASES[self._filler_count % len(FILLER_PHRASES)]
        self._filler_count += 1
        return phrase

    async def _run(
        self,
        context: RunContext,
        tool: str,
        arguments: dict[str, Any],
        call: Callable[[], Awaitable[BaseModel | None]],
        summarize: Callable[[Any], dict[str, Any]],
    ) -> dict[str, Any]:
        query_id = uuid.uuid4().hex[:12]
        clean_args = {k: v for k, v in arguments.items() if v not in (None, "")}
        dropped, self._dropped = self._dropped, []
        if dropped:
            clean_args["filtros_descartados"] = ", ".join(dropped)
        self._events.publish(
            "ips.query.started",
            {"query_id": query_id, "tool": tool, "arguments": clean_args},
        )
        requests_before = self._service.network_requests
        start_ms = self._latency.relative_ms() if self._latency else None
        http_times: list[float] = []
        call_ms = [0.0]
        if self._latency:
            self._latency.mark("tool_start", numbered=True)

        async def timed_call() -> BaseModel | None:
            token = http_durations_ms.set(http_times)
            began = time.perf_counter()
            try:
                return await call()
            finally:
                call_ms[0] = (time.perf_counter() - began) * 1000
                http_durations_ms.reset(token)

        try:
            if self._filler_delay_s is None:
                result = await timed_call()
            else:
                async with context.with_filler(
                    self._filler, delay=self._filler_delay_s, max_steps=1
                ):
                    result = await timed_call()
        except DomainError as exc:
            self._fail(query_id, tool, clean_args, str(exc))
            raise ToolError(str(exc)) from exc
        except SocrataError as exc:
            logger.warning("tool %s failed: %r", tool, exc)
            self._fail(query_id, tool, clean_args, exc.user_message)
            raise ToolError(exc.user_message + " No hay datos para responder.") from exc
        finally:
            if self._latency is not None:
                self._latency.mark("tool_end", numbered=True)
                self._latency.on_tool(
                    ToolTiming(
                        tool=tool,
                        duration_ms=round(call_ms[0], 1),
                        cache_hit=self._service.network_requests == requests_before,
                        http_ms=round(sum(http_times), 1),
                        start_ms=start_ms,
                        end_ms=self._latency.relative_ms(),
                    )
                )
        self._events.publish(
            "ips.query.completed",
            {
                "query_id": query_id,
                "tool": tool,
                "arguments": clean_args,
                "result": result.model_dump(mode="json")
                if result is not None
                else None,
            },
        )
        summary = summarize(result)
        if dropped:
            summary["filtros_descartados_no_mencionados"] = dropped
        return summary

    def _fail(
        self, query_id: str, tool: str, args: dict[str, Any], message: str
    ) -> None:
        self._events.publish(
            "ips.query.failed",
            {"query_id": query_id, "tool": tool, "arguments": args, "message": message},
        )

    @function_tool
    async def count_ips(
        self,
        context: RunContext,
        departamento: str | None = None,
        municipio: str | None = None,
        naturaleza: Literal["Pública", "Privada", "Mixta"] | None = None,
        nivel_atencion: Literal["1", "2", "3", "sin dato"] | None = None,
        grupo_capacidad: str | None = None,
    ) -> dict[str, Any]:
        """Cuenta registros, sedes únicas y prestadores únicos de IPS con filtros opcionales.

        Úsala para preguntas de "cuántas IPS/sedes/prestadores hay" en Colombia o en un lugar.
        Usa una sola llamada y solo los filtros que el usuario mencionó; no desgloses por
        naturaleza ni por nivel (para comparar, usa group_ips).

        Args:
            departamento: Departamento o distrito tal como lo dice el usuario (ej. "Quindío", "Bogotá").
            municipio: Municipio tal como lo dice el usuario (ej. "Armenia").
            naturaleza: Naturaleza jurídica.
            nivel_atencion: Nivel de atención.
            grupo_capacidad: Tipo de capacidad instalada (ej. "camas", "ambulancias", "consultorios", "salas").
        """
        request = FilterRequest(
            departamento=departamento,
            municipio=municipio,
            naturaleza=naturaleza,
            nivel_atencion=nivel_atencion,
            grupo_capacidad=grupo_capacidad,
        )
        request = self._guard(request)
        return await self._run(
            context,
            "count_ips",
            request.model_dump(),
            lambda: self._service.count(request),
            lambda r: {
                "prestadores_unicos": r.prestadores,
                "sedes_unicas": r.sedes,
                "registros": r.registros,
                "filtros_aplicados": r.metadata.filters,
                "limitaciones": spoken_limitations(r.metadata.limitations),
            },
        )

    @function_tool
    async def group_ips(
        self,
        context: RunContext,
        dimension: DimensionName,
        metrica: MetricName = "prestadores",
        top_n: int = 10,
        orden: Literal["mayor_a_menor", "menor_a_mayor"] = "mayor_a_menor",
        departamento: str | None = None,
        municipio: str | None = None,
        naturaleza: Literal["Pública", "Privada", "Mixta"] | None = None,
        nivel_atencion: Literal["1", "2", "3", "sin dato"] | None = None,
        grupo_capacidad: str | None = None,
    ) -> dict[str, Any]:
        """Agrupa y ordena por una dimensión: rankings, comparaciones y distribuciones.

        Ejemplos: departamentos con más prestadores, públicas vs privadas, niveles de atención
        presentes, municipios de un departamento, cantidad de camas por tipo
        (dimension=descripcion_capacidad, metrica=capacidad_instalada, grupo_capacidad="camas").

        Args:
            dimension: Columna por la que se agrupa.
            metrica: prestadores (únicos), sedes (únicas), registros (filas) o capacidad_instalada (suma de cantidades).
            top_n: Número de grupos a devolver (1 a 40).
            orden: Orden del ranking.
            departamento: Filtro opcional de departamento o distrito.
            municipio: Filtro opcional de municipio.
            naturaleza: Filtro opcional de naturaleza jurídica.
            nivel_atencion: Filtro opcional de nivel de atención.
            grupo_capacidad: Filtro opcional de tipo de capacidad.
        """
        request = FilterRequest(
            departamento=departamento,
            municipio=municipio,
            naturaleza=naturaleza,
            nivel_atencion=nivel_atencion,
            grupo_capacidad=grupo_capacidad,
        )
        request = self._guard(request)
        if dimension not in _DIMENSIONS:
            raise ToolError(f"Dimensión no permitida: {dimension}")
        return await self._run(
            context,
            "group_ips",
            {
                "dimension": dimension,
                "metrica": metrica,
                "top_n": top_n,
                **request.model_dump(),
            },
            lambda: self._service.group(
                _DIMENSIONS[dimension],
                Metric(metrica),
                request,
                top_n=top_n,
                ascending=orden == "menor_a_mayor",
            ),
            lambda r: {
                "unidad": r.metric_description,
                "grupos": [{"valor": b.label, "total": b.value} for b in r.buckets],
                "filtros_aplicados": r.metadata.filters,
                "limitaciones": spoken_limitations(r.metadata.limitations),
            },
        )

    @function_tool
    async def search_ips(
        self,
        context: RunContext,
        nombre: str | None = None,
        departamento: str | None = None,
        municipio: str | None = None,
        naturaleza: Literal["Pública", "Privada", "Mixta"] | None = None,
        pagina: int = 1,
    ) -> dict[str, Any]:
        """Busca sedes de IPS por nombre (o parte) y/o ubicación. Devuelve hasta 10 por página.

        Args:
            nombre: Parte del nombre del prestador o de la sede (ej. "San Juan de Dios").
            departamento: Departamento o distrito.
            municipio: Municipio.
            naturaleza: Naturaleza jurídica.
            pagina: Página de resultados, desde 1.
        """
        request = FilterRequest(
            nombre=nombre,
            departamento=departamento,
            municipio=municipio,
            naturaleza=naturaleza,
        )
        request = self._guard(request)
        if not any([nombre, departamento, municipio]):
            raise ToolError(
                "Indica al menos un nombre, departamento o municipio para buscar."
            )
        return await self._run(
            context,
            "search_ips",
            {**request.model_dump(), "pagina": pagina},
            lambda: self._service.search(request, page=pagina, page_size=10),
            lambda r: {
                "total_sedes_encontradas": r.total_sedes,
                "pagina": r.page,
                "sedes": [
                    {
                        "codigo_sede": i.codigo_sede,
                        "sede": i.nombre_sede,
                        "prestador": i.nombre_prestador,
                        "municipio": i.municipio,
                        "departamento": i.departamento,
                        "naturaleza": i.naturaleza,
                    }
                    for i in r.items
                ],
                "filtros_aplicados": r.metadata.filters,
                "limitaciones": spoken_limitations(r.metadata.limitations),
            },
        )

    @function_tool
    async def get_ips_details(
        self, context: RunContext, codigo_sede: str
    ) -> dict[str, Any]:
        """Detalle de una sede: prestador, ubicación, naturaleza, nivel y capacidad instalada.

        Usa el codigo_sede devuelto por search_ips; nunca inventes códigos.

        Args:
            codigo_sede: Código numérico de la sede obtenido de search_ips.
        """

        async def call() -> BaseModel | None:
            detail = await self._service.details(codigo_sede)
            if detail is None:
                raise DomainError(
                    f"No existe una sede con código {codigo_sede} en la fuente oficial."
                )
            return detail

        return await self._run(
            context,
            "get_ips_details",
            {"codigo_sede": codigo_sede},
            call,
            lambda r: {
                "sede": r.site.nombre_sede,
                "prestador": r.site.nombre_prestador,
                "municipio": r.site.municipio,
                "departamento": r.site.departamento,
                "naturaleza": r.site.naturaleza,
                "nivel_atencion": r.site.nivel_atencion or "sin dato",
                "direccion": r.site.direccion,
                "capacidad_instalada": [
                    {"grupo": c.grupo, "tipo": c.descripcion, "cantidad": c.cantidad}
                    for c in r.capacidades
                ],
                "fecha_corte": r.fecha_corte,
            },
        )

    @function_tool
    async def get_dataset_overview(self, context: RunContext) -> dict[str, Any]:
        """Describe la fuente oficial: nombre, cobertura, totales, campos, fecha de corte y límites.

        Úsala cuando pregunten qué datos hay, de cuándo son o qué no se puede saber con la fuente.
        """
        return await self._run(
            context,
            "get_dataset_overview",
            {},
            self._service.overview,
            lambda r: {
                "nombre": r.name,
                "publicado_por": r.attribution,
                "actualizado": r.rows_updated_at.date().isoformat()
                if r.rows_updated_at
                else None,
                "prestadores_unicos": r.totals.prestadores,
                "sedes_unicas": r.totals.sedes,
                "registros": r.totals.registros,
                "campos": r.fields,
                "limitaciones": r.limitations,
            },
        )
