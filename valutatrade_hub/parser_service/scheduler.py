"""Планировщик периодического обновления курсов."""

import time

from valutatrade_hub.parser_service.updater import RatesUpdater


class RatesScheduler:
    """Запускает RatesUpdater с заданным интервалом."""

    def __init__(self, updater: RatesUpdater, interval_seconds: int) -> None:
        self.updater = updater
        self.interval_seconds = interval_seconds

    def run(self, iterations: int | None = None) -> None:
        """Обновлять курсы iterations раз (None — бесконечно, до Ctrl+C)."""
        count = 0
        while iterations is None or count < iterations:
            self.updater.run_update()
            count += 1
            if iterations is None or count < iterations:
                time.sleep(self.interval_seconds)
