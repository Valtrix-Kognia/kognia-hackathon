class DomainError(Exception):
    """Errors whose message is safe to show to the user and to the LLM."""


class UnknownFilterValueError(DomainError):
    def __init__(self, field: str, raw_value: str, suggestions: list[str]) -> None:
        self.field = field
        self.raw_value = raw_value
        self.suggestions = suggestions
        hint = f" Valores parecidos: {', '.join(suggestions)}." if suggestions else ""
        super().__init__(
            f"El valor '{raw_value}' no existe para '{field}' en la fuente oficial.{hint}"
        )


class InvalidIdentifierError(DomainError):
    pass
