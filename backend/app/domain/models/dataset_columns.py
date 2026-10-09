from enum import StrEnum


class Column(StrEnum):
    """Whitelisted technical column ids of dataset s2ru-bqt6 (verified against the live API)."""

    DEPARTAMENTO = "departamento"
    MUNICIPIO = "municipio"
    CODIGO_PRESTADOR = "c_digo_prestador"
    NOMBRE_PRESTADOR = "nombre_prestador"
    NIT = "nit_ips"
    NATURALEZA = "naturaleza"
    NIVEL_ATENCION = "num_nivel_atencion"
    CODIGO_SEDE = "c_digo_sede"
    NUMERO_SEDE = "n_mero_sede"
    NOMBRE_SEDE = "nom_sede_ips"
    DIRECCION = "direcci_n"
    TELEFONO = "tel_fono"
    GRUPO_CAPACIDAD = "nom_grupo_capacidad"
    DESCRIPCION_CAPACIDAD = "nom_descripcion_capacidad"
    CANTIDAD_CAPACIDAD = "num_cantidad_capacidad_instalada"
    FECHA_CORTE = "fecha_corte"
    FUENTE = "fuente"


class Dimension(StrEnum):
    """Columns that may be used for GROUP BY."""

    DEPARTAMENTO = Column.DEPARTAMENTO.value
    MUNICIPIO = Column.MUNICIPIO.value
    NATURALEZA = Column.NATURALEZA.value
    NIVEL_ATENCION = Column.NIVEL_ATENCION.value
    GRUPO_CAPACIDAD = Column.GRUPO_CAPACIDAD.value
    DESCRIPCION_CAPACIDAD = Column.DESCRIPCION_CAPACIDAD.value


class Metric(StrEnum):
    """Units of analysis. A dataset row is one installed-capacity line, not one IPS."""

    REGISTROS = "registros"
    PRESTADORES = "prestadores"
    SEDES = "sedes"
    CAPACIDAD_INSTALADA = "capacidad_instalada"


METRIC_EXPRESSIONS: dict[Metric, str] = {
    Metric.REGISTROS: "count(*)",
    Metric.PRESTADORES: f"count(DISTINCT {Column.CODIGO_PRESTADOR})",
    Metric.SEDES: f"count(DISTINCT {Column.CODIGO_SEDE})",
    Metric.CAPACIDAD_INSTALADA: f"sum({Column.CANTIDAD_CAPACIDAD})",
}

METRIC_DESCRIPTIONS: dict[Metric, str] = {
    Metric.REGISTROS: "filas del dataset (cada fila es una línea de capacidad instalada de una sede)",
    Metric.PRESTADORES: "prestadores únicos según código de prestador REPS",
    Metric.SEDES: "sedes únicas según código de sede REPS",
    Metric.CAPACIDAD_INSTALADA: "suma de la cantidad de capacidad instalada reportada",
}
