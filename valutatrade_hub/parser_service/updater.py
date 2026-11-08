"""Координация обновления курсов из всех источников."""

import logging
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import utc_now_iso
from valutatrade_hub.logging_config import PARSER_LOGGER
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = logging.getLogger(PARSER_LOGGER)

SOURCES: dict[str, type[BaseApiClient]] = {
    "coingecko": CoinGeckoClient,
    "exchangerate": ExchangeRateApiClient,
}


class RatesUpdater:
    """Опрашивает клиентов, объединяет курсы и сохраняет их."""

    def __init__(self, clients: list[BaseApiClient], storage: RatesStorage) -> None:
        self.clients = clients
        self.storage = storage

    def run_update(self) -> dict[str, Any]:
        """Обновить курсы; падение одного источника не останавливает остальные."""
        logger.info("Starting rates update...")
        timestamp = utc_now_iso()
        snapshot: dict[str, dict] = {}
        history: list[dict] = []
        errors: list[str] = []

        for client in self.clients:
            try:
                rates = client.fetch_rates()
            except ApiRequestError as error:
                logger.error(
                    "Failed to fetch from %s: %s", client.source_name, error.reason
                )
                errors.append(error.reason)
                continue
            logger.info(
                "Fetching from %s... OK (%d rates)", client.source_name, len(rates)
            )
            for pair, rate in rates.items():
                snapshot[pair] = {
                    "rate": rate,
                    "updated_at": timestamp,
                    "source": client.source_name,
                }
                from_code, to_code = pair.split("_")
                history.append(
                    {
                        "id": f"{pair}_{timestamp}",
                        "from_currency": from_code,
                        "to_currency": to_code,
                        "rate": rate,
                        "timestamp": timestamp,
                        "source": client.source_name,
                        "meta": {
                            "raw_id": client.raw_ids.get(pair),
                            **client.last_meta,
                        },
                    }
                )

        if snapshot:
            logger.info(
                "Writing %d rates to %s...",
                len(snapshot),
                self.storage.config.RATES_FILE_PATH,
            )
            self.storage.save_snapshot(snapshot, timestamp)
            self.storage.append_history(history)
        logger.info("Update finished: %d rates, %d errors", len(snapshot), len(errors))
        return {"updated": len(snapshot), "errors": errors, "last_refresh": timestamp}


def create_updater(source: str | None = None) -> RatesUpdater:
    """Собрать RatesUpdater для всех источников или одного (--source)."""
    config = ParserConfig()
    if source is None:
        names = list(SOURCES)
    else:
        name = source.strip().lower()
        if name not in SOURCES:
            available = ", ".join(SOURCES)
            raise ValueError(f"Неизвестный источник '{source}'. Доступно: {available}")
        names = [name]
    clients = [SOURCES[name](config) for name in names]
    return RatesUpdater(clients, RatesStorage(config))
