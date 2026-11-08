"""Клиенты внешних API: единый интерфейс fetch_rates() -> dict."""

import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

HTTP_OK = 200
HTTP_ERROR_MESSAGES = {
    401: "неверный или отсутствующий API-ключ (401)",
    403: "доступ запрещён, проверьте API-ключ (403)",
    404: "ресурс не найден (404)",
    429: "превышен лимит запросов (429), подождите и повторите",
}


class BaseApiClient(ABC):
    """Базовый клиент: HTTP-запрос, проверка статуса, обёртка ошибок."""

    source_name = "Unknown"

    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self.last_meta: dict[str, Any] = {}
        self.raw_ids: dict[str, str] = {}

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Вернуть курсы в формате {'BTC_USD': 59337.21, ...}."""

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        """GET-запрос с таймаутом; любые сбои → ApiRequestError."""
        started = time.perf_counter()
        try:
            response = requests.get(
                url, params=params, timeout=self.config.REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"{self.source_name}: превышено время ожидания"
            ) from None
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(
                f"{self.source_name}: сетевая ошибка ({type(error).__name__})"
            ) from None

        self.last_meta = {
            "request_ms": int((time.perf_counter() - started) * 1000),
            "status_code": response.status_code,
            "etag": response.headers.get("ETag"),
        }
        if response.status_code != HTTP_OK:
            reason = HTTP_ERROR_MESSAGES.get(
                response.status_code, f"HTTP {response.status_code}"
            )
            raise ApiRequestError(f"{self.source_name}: {reason}")
        try:
            return response.json()
        except ValueError:
            raise ApiRequestError(
                f"{self.source_name}: некорректный JSON в ответе"
            ) from None


def _is_positive_number(value: Any) -> bool:
    """Проверка типа данных курса."""
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


class CoinGeckoClient(BaseApiClient):
    """Курсы криптовалют (CoinGecko, без ключа)."""

    source_name = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        base = self.config.BASE_CURRENCY
        ids = [
            self.config.CRYPTO_ID_MAP[code] for code in self.config.CRYPTO_CURRENCIES
        ]
        params = {"ids": ",".join(ids), "vs_currencies": base.lower()}
        data = self._get_json(self.config.COINGECKO_URL, params)

        rates: dict[str, float] = {}
        for code in self.config.CRYPTO_CURRENCIES:
            raw_id = self.config.CRYPTO_ID_MAP[code]
            value = data.get(raw_id, {}).get(base.lower())
            if _is_positive_number(value):
                pair = f"{code}_{base}"
                rates[pair] = float(value)
                self.raw_ids[pair] = raw_id
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет курсов")
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Курсы фиатных валют (ExchangeRate-API, нужен ключ)."""

    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        key = self.config.EXCHANGERATE_API_KEY
        if not key:
            raise ApiRequestError(
                f"{self.source_name}: не задан ключ EXCHANGERATE_API_KEY (.env)"
            )
        base = self.config.BASE_CURRENCY
        url = f"{self.config.EXCHANGERATE_API_URL}/{key}/latest/{base}"
        data = self._get_json(url)
        if data.get("result") != "success":
            reason = data.get("error-type", "неизвестная ошибка")
            raise ApiRequestError(f"{self.source_name}: {reason}")

        rates: dict[str, float] = {}
        raw_rates = data.get("conversion_rates") or data.get("rates", {})
        for code in self.config.FIAT_CURRENCIES:
            value = raw_rates.get(code)
            if _is_positive_number(value):
                # API отдаёт «1 USD = value CODE», в кеше храним «1 CODE = x USD»
                pair = f"{code}_{base}"
                rates[pair] = round(1 / float(value), 8)
                self.raw_ids[pair] = code
        if not rates:
            raise ApiRequestError(f"{self.source_name}: в ответе нет курсов")
        return rates
