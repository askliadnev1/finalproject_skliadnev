"""Пользовательские (доменные) исключения ValutaTrade Hub."""


class ValutaTradeError(Exception):
    """Базовое исключение приложения."""


class InsufficientFundsError(ValutaTradeError):
    """Недостаточно средств на кошельке."""

    def __init__(self, available: float, required: float, code: str) -> None:
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class CurrencyNotFoundError(ValutaTradeError):
    """Неизвестный код валюты."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(ValutaTradeError):
    """Сбой при обращении к внешнему API или источнику курсов."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")


class AuthenticationError(ValutaTradeError):
    """Ошибки регистрации, входа и отсутствия сессии."""


class WalletNotFoundError(ValutaTradeError):
    """У пользователя нет кошелька в указанной валюте."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(
            f"У вас нет кошелька '{code}'. Добавьте валюту: "
            "она создаётся автоматически при первой покупке."
        )


class RateUnavailableError(ValutaTradeError):
    """Курс недоступен: нет данных в кеше и не удалось обновить."""

    def __init__(
        self, from_code: str, to_code: str, message: str | None = None
    ) -> None:
        self.from_code = from_code
        self.to_code = to_code
        default = f"Курс {from_code}→{to_code} недоступен. Повторите попытку позже."
        super().__init__(message or default)
