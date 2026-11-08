"""Конфигурация Parser Service: ключи, эндпоинты, валюты, пути, таймауты."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

API_KEY_ENV = "EXCHANGERATE_API_KEY"
ENV_FILE = Path(".env")


def load_env_file(path: Path = ENV_FILE) -> None:
    """Загрузить переменные из .env, не перезаписывая уже заданные."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))


load_env_file()


def _settings_value(key: str) -> str:
    """Значение из SettingsLoader в виде строки."""
    return str(SettingsLoader().get(key))


@dataclass(frozen=True)
class ParserConfig:
    """Все изменяемые параметры Parser Service в одном месте."""

    EXCHANGERATE_API_KEY: str | None = field(
        default_factory=lambda: os.getenv(API_KEY_ENV)
    )
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict[str, str] = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    RATES_FILE_PATH: str = field(default_factory=lambda: _settings_value("rates_file"))
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: _settings_value("history_file")
    )

    REQUEST_TIMEOUT: int = 10
    UPDATE_INTERVAL_SECONDS: int = 300
