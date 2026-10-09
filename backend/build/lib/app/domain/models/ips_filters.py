from pydantic import BaseModel, ConfigDict, Field


class IpsFilters(BaseModel):
    """Filters already resolved to canonical dataset values."""

    model_config = ConfigDict(frozen=True)

    departamento: str | None = None
    municipios: tuple[str, ...] = ()
    naturaleza: str | None = None
    nivel_atencion: str | None = None
    grupo_capacidad: str | None = None
    nombre: str | None = Field(default=None, max_length=80)

    def describe(self) -> dict[str, str]:
        applied: dict[str, str] = {}
        if self.departamento:
            applied["departamento"] = self.departamento
        if self.municipios:
            applied["municipio"] = ", ".join(self.municipios)
        if self.naturaleza:
            applied["naturaleza"] = self.naturaleza
        if self.nivel_atencion:
            applied["nivel_atencion"] = self.nivel_atencion
        if self.grupo_capacidad:
            applied["grupo_capacidad"] = self.grupo_capacidad
        if self.nombre:
            applied["nombre_contiene"] = self.nombre
        return applied
