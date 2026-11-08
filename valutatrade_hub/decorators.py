"""Декоратор @log_action для логирования доменных операций."""

import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any

from valutatrade_hub.logging_config import ACTIONS_LOGGER

logger = logging.getLogger(ACTIONS_LOGGER)


def _fmt_number(value: Any, digits: int) -> str:
    """Отформатировать число, если это число, иначе вернуть repr."""
    if isinstance(value, int | float):
        return f"{value:.{digits}f}"
    return repr(value)


def log_action(action: str, verbose: bool = False) -> Callable:
    """Логировать вызов операции (BUY/SELL/REGISTER/LOGIN).

    Исключения не глотаются: они пишутся в лог и пробрасываются дальше.
    При verbose=True в лог добавляется состояние кошелька «было→стало».
    """

    def decorator(func: Callable) -> Callable:
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            params = signature.bind_partial(*args, **kwargs).arguments
            parts = [action]
            user = params.get("username") or params.get("user_id")
            if user is not None:
                parts.append(f"user='{user}'")
            if "currency_code" in params:
                parts.append(f"currency='{params['currency_code']}'")
            if "amount" in params:
                parts.append(f"amount={_fmt_number(params['amount'], 4)}")

            try:
                result = func(*args, **kwargs)
            except Exception as error:
                parts.append("result=ERROR")
                parts.append(f"error_type={type(error).__name__}")
                parts.append(f"error_message='{error}'")
                logger.info(" ".join(parts))
                raise

            if isinstance(result, dict):
                if result.get("rate") is not None:
                    parts.append(f"rate={_fmt_number(result['rate'], 2)}")
                    parts.append(f"base='{result.get('base', 'USD')}'")
                if verbose and "before" in result and "after" in result:
                    before = _fmt_number(result["before"], 4)
                    after = _fmt_number(result["after"], 4)
                    parts.append(f"wallet={before}->{after}")
            parts.append("result=OK")
            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
