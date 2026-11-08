"""Хранилище Parser Service: rates.json (снимок) и exchange_rates.json (история)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from valutatrade_hub.core.utils import parse_iso
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


def _to_datetime(timestamp: str | None) -> datetime | None:
    """ISO-строка → datetime с часовым поясом."""
    if not timestamp:
        return None
    moment = parse_iso(timestamp)
    return moment if moment.tzinfo else moment.astimezone()


class RatesStorage:
    """Чтение и атомарная запись файлов курсов."""

    def __init__(self, config: ParserConfig) -> None:
        self.config = config
        self._db = DatabaseManager()

    def load_snapshot(self) -> dict[str, Any]:
        """Прочитать снимок текущих курсов."""
        data = self._db.read_json(Path(self.config.RATES_FILE_PATH), {})
        data.setdefault("pairs", {})
        data.setdefault("last_refresh", None)
        return data

    def save_snapshot(self, rates: dict[str, dict], last_refresh: str) -> None:
        """Обновить снимок: пара заменяется, только если данные не старее."""
        snapshot = self.load_snapshot()
        for pair, info in rates.items():
            current = snapshot["pairs"].get(pair)
            current_time = _to_datetime(current.get("updated_at")) if current else None
            new_time = _to_datetime(info["updated_at"])
            if current_time is None or new_time >= current_time:
                snapshot["pairs"][pair] = info
        snapshot["last_refresh"] = last_refresh
        self._db.write_json(Path(self.config.RATES_FILE_PATH), snapshot)

    def append_history(self, records: list[dict]) -> int:
        """Добавить записи в историю без дублей по id; вернуть число новых."""
        path = Path(self.config.HISTORY_FILE_PATH)
        history = self._db.read_json(path, [])
        if not isinstance(history, list):
            history = []
        known_ids = {record.get("id") for record in history}
        new_records = [record for record in records if record["id"] not in known_ids]
        history.extend(new_records)
        self._db.write_json(path, history)
        return len(new_records)
