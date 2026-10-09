from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.models.dataset_columns import Metric


class QueryMetadata(BaseModel):
    dataset_id: str
    source: str
    queried_at: datetime
    filters: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class CountResult(BaseModel):
    registros: int
    prestadores: int
    sedes: int
    metadata: QueryMetadata


class GroupBucket(BaseModel):
    label: str
    value: float


class GroupResult(BaseModel):
    dimension: str
    metric: Metric
    metric_description: str
    buckets: list[GroupBucket]
    metadata: QueryMetadata


class IpsSite(BaseModel):
    codigo_sede: str
    nombre_sede: str
    codigo_prestador: str
    nombre_prestador: str
    departamento: str
    municipio: str
    naturaleza: str | None = None
    nivel_atencion: str | None = None
    direccion: str | None = None
    telefono: str | None = None


class SearchResult(BaseModel):
    total_sedes: int
    page: int
    page_size: int
    items: list[IpsSite]
    metadata: QueryMetadata


class CapacityLine(BaseModel):
    grupo: str
    descripcion: str
    cantidad: float


class IpsDetail(BaseModel):
    site: IpsSite
    capacidades: list[CapacityLine]
    fecha_corte: str | None = None
    metadata: QueryMetadata


class DatasetOverview(BaseModel):
    name: str
    description: str
    attribution: str | None
    rows_updated_at: datetime | None
    totals: CountResult
    fields: dict[str, str]
    limitations: list[str]
