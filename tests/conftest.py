import pytest

from app import main
from app.ratelimit import RateLimiter


@pytest.fixture(autouse=True)
def no_model_loading(monkeypatch):
    """Les tests ne chargent ni ne téléchargent jamais de modèle."""
    monkeypatch.setattr(main, "warm_up_models", lambda: None)


@pytest.fixture(autouse=True)
def generous_rate_limiter(monkeypatch):
    """Un compteur neuf et très large pour chaque test."""
    monkeypatch.setattr(main, "rate_limiter", RateLimiter(10_000, 60))