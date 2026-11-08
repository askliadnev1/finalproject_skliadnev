"""Иерархия валют: Currency, FiatCurrency, CryptoCurrency и реестр."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

MIN_CODE_LENGTH = 2
MAX_CODE_LENGTH = 5


class Currency(ABC):
    """Абстрактная валюта с человекочитаемым именем и кодом."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        if (
            not isinstance(code, str)
            or code != code.upper()
            or not code.isalnum()
            or not MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH
        ):
            raise ValueError(
                "Код валюты должен быть в верхнем регистре, 2–5 символов, без пробелов"
            )
        self.name = name
        self.code = code

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для UI и логов."""


class FiatCurrency(Currency):
    """Фиатная валюта с указанием страны или зоны эмиссии."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self) -> str:
        """Вернуть строку вида '[FIAT] USD — US Dollar (Issuing: ...)'."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и рыночной капитализацией."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        """Вернуть строку вида '[CRYPTO] BTC — Bitcoin (Algo: ..., MCAP: ...)'."""
        mcap = f"{self.market_cap:.2e}".replace("e+", "e")
        return (
            f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap})"
        )


_CURRENCY_REGISTRY: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.5e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 6.5e10),
}


def get_currency(code: str) -> Currency:
    """Вернуть валюту по коду или бросить CurrencyNotFoundError."""
    normalized = code.strip().upper() if isinstance(code, str) else ""
    if normalized not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(code)
    return _CURRENCY_REGISTRY[normalized]


def get_supported_codes() -> list[str]:
    """Список поддерживаемых кодов валют."""
    return sorted(_CURRENCY_REGISTRY)
