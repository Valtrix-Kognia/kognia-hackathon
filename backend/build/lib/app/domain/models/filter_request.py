from pydantic import BaseModel, ConfigDict, Field


class FilterRequest(BaseModel):
    """Raw filter values as spoken/typed by a user, before catalog resolution."""

    model_config = ConfigDict(str_strip_whitespace=True)

    departamento: str | None = Field(default=None, max_length=60)
    municipio: str | None = Field(default=None, max_length=60)
    naturaleza: str | None = Field(default=None, max_length=20)
    nivel_atencion: str | None = Field(default=None, max_length=30)
    grupo_capacidad: str | None = Field(default=None, max_length=40)
    nombre: str | None = Field(default=None, max_length=80)
