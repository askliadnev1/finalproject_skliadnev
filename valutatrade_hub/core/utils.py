"""Вспомогательные функции: валидация, хеширование, даты, конвертация."""

import hashlib
import math
import secrets
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from valutatrade_hub.core.currencies import (
    MAX_CODE_LENGTH,
    MIN_CODE_LENGTH,
    CryptoCurrency,
    get_currency,
)
from valutatrade_hub.core.exceptions import CurrencyNotFoundError

BASE_CURRENCY = "USD"
MIN_PASSWORD_LENGTH = 4
SALT_BYTES = 8
BALANCE_PRECISION = 8
CRYPTO_DECIMALS = 4
FIAT_DECIMALS = 2

AMOUNT_ERROR = "'amount' должен быть положительным числом"

# Заглушка курсов (1 единица валюты = N USD), если кеш rates.json пуст.
STUB_RATES_TO_USD: dict[str, float] = {
    "EUR_USD": 1.07,
    "GBP_USD": 1.25,
    "RUB_USD": 0.01016,
    "BTC_USD": 59300.0,
    "ETH_USD": 3720.0,
    "SOL_USD": 145.12,
}


def validate_currency_code(code: Any) -> str:
    """Проверить формат кода валюты и привести его к верхнему регистру."""
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Код валюты должен быть непустой строкой")
    normalized = code.strip().upper()
    if (
        not normalized.isalnum()
        or not MIN_CODE_LENGTH <= len(normalized) <= MAX_CODE_LENGTH
    ):
        raise ValueError(f"Некорректный код валюты '{code}'")
    return normalized


def validate_amount(amount: Any) -> float:
    """Проверить, что amount — положительное конечное число."""
    if isinstance(amount, bool):
        raise ValueError(AMOUNT_ERROR)
    try:
        value = float(amount)
    except (TypeError, ValueError):
        raise ValueError(AMOUNT_ERROR) from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(AMOUNT_ERROR)
    return value


def validate_username(username: Any) -> str:
    """Проверить, что имя пользователя — непустая строка."""
    if not isinstance(username, str) or not username.strip():
        raise ValueError("Имя пользователя не может быть пустым")
    return username.strip()


def validate_password(password: Any) -> str:
    """Проверить минимальную длину пароля."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
    return password


def generate_salt() -> str:
    """Сгенерировать случайную соль."""
    return secrets.token_hex(SALT_BYTES)


def hash_password(password: str, salt: str) -> str:
    """Односторонний хеш SHA-256 от пароля с солью."""
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


def now_iso() -> str:
    """Текущее локальное время в формате ISO (до секунд)."""
    return datetime.now().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    """Разобрать строку ISO-даты (поддерживает суффикс 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def get_rate_to_usd(code: str, pairs: Mapping[str, float]) -> float | None:
    """Курс валюты к USD из словаря вида {'BTC_USD': 59300.0}."""
    if code == BASE_CURRENCY:
        return 1.0
    return pairs.get(f"{code}_{BASE_CURRENCY}")


def convert_rate(
    from_code: str, to_code: str, pairs: Mapping[str, float]
) -> float | None:
    """Кросс-курс from→to через USD; None, если курса нет."""
    from_usd = get_rate_to_usd(from_code, pairs)
    to_usd = get_rate_to_usd(to_code, pairs)
    if from_usd is None or not to_usd:
        return None
    return from_usd / to_usd


def is_crypto(code: str) -> bool:
    """Является ли валюта криптовалютой."""
    try:
        return isinstance(get_currency(code), CryptoCurrency)
    except CurrencyNotFoundError:
        return False


def format_balance(code: str, value: float) -> str:
    """Баланс: 4 знака для крипты, 2 знака для фиата."""
    digits = CRYPTO_DECIMALS if is_crypto(code) else FIAT_DECIMALS
    return f"{value:.{digits}f}"


def format_money(value: float) -> str:
    """Денежная сумма с разделителем тысяч: 3,329.00."""
    return f"{value:,.2f}"
