import pytest

from app.config.settings import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:4200", ["http://localhost:4200"]),
        (
            "https://a.example, https://b.example",
            ["https://a.example", "https://b.example"],
        ),
        ('["https://a.example"]', ["https://a.example"]),
    ],
)
def test_cors_origins_from_environment(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str]
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings(_env_file=None).cors_origins == expected
