"""Singleton DatabaseManager: абстракция над JSON-хранилищем."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Безопасное чтение и атомарная запись JSON-файлов проекта.

    Singleton реализован через __new__, как и SettingsLoader.
    """

    _instance: "DatabaseManager | None" = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = SettingsLoader()
            cls._instance = instance
        return cls._instance

    @staticmethod
    def read_json(path: Path, default: Any) -> Any:
        """Прочитать JSON; при отсутствии или порче файла вернуть default."""
        if not path.exists() or path.stat().st_size == 0:
            return default
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            return default

    @staticmethod
    def write_json(path: Path, data: Any) -> None:
        """Атомарно записать JSON: временный файл, затем rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    def load_users(self) -> list[dict]:
        """Загрузить список пользователей."""
        return self.read_json(self._settings.path("users_file"), [])

    def save_users(self, users: list[dict]) -> None:
        """Сохранить список пользователей."""
        self.write_json(self._settings.path("users_file"), users)

    def load_portfolios(self) -> list[dict]:
        """Загрузить список портфелей."""
        return self.read_json(self._settings.path("portfolios_file"), [])

    def save_portfolios(self, portfolios: list[dict]) -> None:
        """Сохранить список портфелей."""
        self.write_json(self._settings.path("portfolios_file"), portfolios)

    def load_rates(self) -> dict:
        """Загрузить кеш курсов (rates.json)."""
        data = self.read_json(self._settings.path("rates_file"), {})
        data.setdefault("pairs", {})
        data.setdefault("last_refresh", None)
        return data

    def save_rates(self, rates: dict) -> None:
        """Сохранить кеш курсов (rates.json)."""
        self.write_json(self._settings.path("rates_file"), rates)
