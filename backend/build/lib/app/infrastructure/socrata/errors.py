class SocrataError(Exception):
    """Base error for the official data source. user_message is safe to show to users."""

    user_message = "No fue posible consultar la fuente oficial de datos."


class SocrataUnavailableError(SocrataError):
    user_message = "La API oficial de datos.gov.co no está disponible en este momento."


class SocrataTimeoutError(SocrataUnavailableError):
    user_message = "La API oficial de datos.gov.co tardó demasiado en responder."


class SocrataRateLimitError(SocrataUnavailableError):
    user_message = "La API oficial limitó temporalmente las consultas. Intenta de nuevo en unos segundos."


class SocrataAuthError(SocrataError):
    user_message = "La credencial configurada para la API oficial fue rechazada."


class SocrataQueryError(SocrataError):
    user_message = "La consulta no fue aceptada por la API oficial."


class SocrataResponseError(SocrataError):
    user_message = "La API oficial devolvió una respuesta inesperada."
