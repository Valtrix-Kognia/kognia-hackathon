from typing import Any


class FakeSocrataClient:
    """Answers catalog queries with a tiny fixed catalog and records every other SoQL query."""

    def __init__(self, responses: list[list[dict[str, Any]]] | None = None) -> None:
        self.queries: list[str] = []
        self._responses = list(responses or [])

    async def metadata(self) -> dict[str, Any]:
        return {"name": "Relación de IPS", "description": "desc", "rowsUpdatedAt": 1669070228}

    async def query(self, soql: str, page_number: int = 1, page_size: int = 100) -> list[dict[str, Any]]:
        if soql.startswith("SELECT departamento, municipio GROUP BY"):
            return [
                {"departamento": "Quindío", "municipio": "ARMENIA"},
                {"departamento": "Antioquia", "municipio": "ARMENIA"},
                {"departamento": "Antioquia", "municipio": "MEDELLÍN"},
                {"departamento": "Valle del cauca", "municipio": "PALMIRA"},
                {"departamento": "Bogotá D.C", "municipio": "BOGOTÁ"},
            ]
        if soql.startswith("SELECT naturaleza, count(*) AS n"):
            return [{"naturaleza": "Pública", "n": "6"}, {"naturaleza": "Privada", "n": "3"}, {"naturaleza": "Mixta", "n": "1"}]
        if soql.startswith("SELECT num_nivel_atencion, count(*) AS n"):
            return [{"num_nivel_atencion": "1", "n": "3"}, {"num_nivel_atencion": "2", "n": "1"}, {"n": "6"}]
        if soql.startswith("SELECT nom_grupo_capacidad, count(*) AS n"):
            return [{"nom_grupo_capacidad": "CAMAS", "n": "5"}, {"nom_grupo_capacidad": "CONSULTORIOS", "n": "5"}]
        if soql.startswith("SELECT fecha_corte, count(*) AS n"):
            return [{"fecha_corte": "Fecha corte REPS: Nov  5 2022", "n": "10"}]
        self.queries.append(soql)
        return self._responses.pop(0) if self._responses else []
