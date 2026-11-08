"""Конфигурация приложения: Singleton SettingsLoader."""

import tomllib
from pathlib import Path
from typing import Any

BASE_DIR = Path.cwd()
PYPROJECT_PATH = BASE_DIR / "pyproject.toml"

DEFAULT_SETTINGS: dict[str, Any] = {
    "data_dir": "data",
    "users_file": "data/users.json",
    "portfolios_file": "data/portfolios.json",
    "rates_file": "data/rates.json",
    "history_file": "data/exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_level": "INFO",
    "log_max_bytes": 1_000_000,
    "log_backup_count": 5,
}


class SettingsLoader:
    """Единая точка доступа к конфигурации проекта.

    Singleton реализован через __new__: это самый простой и читаемый способ,
    не требующий метаклассов. Любой вызов SettingsLoader() возвращает
    один и тот же объект, поэтому конфигурация читается один раз.
    """

    _instance: "SettingsLoader | None" = None

    def __new__(cls) -> "SettingsLoader":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._settings = {}
            instance.reload()
            cls._instance = instance
        return cls._instance

    def reload(self) -> None:
        """Перечитать настройки из секции [tool.valutatrade] в pyproject.toml."""
        settings = dict(DEFAULT_SETTINGS)
        if PYPROJECT_PATH.exists():
            with PYPROJECT_PATH.open("rb") as file:
                data = tomllib.load(file)
            settings.update(data.get("tool", {}).get("valutatrade", {}))
        self._settings = settings

    def get(self, key: str, default: Any = None) -> Any:
        """Вернуть значение настройки по ключу."""
        return self._settings.get(key, default)

    def path(self, key: str) -> Path:
        """Вернуть абсолютный путь для настройки-пути (например, 'users_file')."""
        return BASE_DIR / self._settings[key]
