"""Настройка логирования: формат, уровень, ротация файлов."""

import logging
from logging.handlers import RotatingFileHandler

from valutatrade_hub.infra.settings import SettingsLoader

LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
CONSOLE_FORMAT = "%(levelname)s: %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

ACTIONS_LOGGER = "valutatrade.actions"
PARSER_LOGGER = "valutatrade.parser"


def _file_handler(filename: str, settings: SettingsLoader) -> RotatingFileHandler:
    """Создать обработчик файла с ротацией по размеру."""
    log_dir = settings.path("log_dir")
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / filename,
        maxBytes=settings.get("log_max_bytes", 1_000_000),
        backupCount=settings.get("log_backup_count", 5),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def setup_logging() -> None:
    """Настроить логгеры действий (actions.log) и парсера (parser.log)."""
    settings = SettingsLoader()
    level_name = str(settings.get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    actions_logger = logging.getLogger(ACTIONS_LOGGER)
    if not actions_logger.handlers:
        actions_logger.setLevel(level)
        actions_logger.addHandler(_file_handler("actions.log", settings))
        actions_logger.propagate = False

    parser_logger = logging.getLogger(PARSER_LOGGER)
    if not parser_logger.handlers:
        parser_logger.setLevel(level)
        parser_logger.addHandler(_file_handler("parser.log", settings))
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
        parser_logger.addHandler(console)
        parser_logger.propagate = False
