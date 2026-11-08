"""Доменные модели: User, Wallet, Portfolio."""

import hmac
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from valutatrade_hub.core.exceptions import ApiRequestError, InsufficientFundsError
from valutatrade_hub.core.utils import (
    BALANCE_PRECISION,
    BASE_CURRENCY,
    STUB_RATES_TO_USD,
    convert_rate,
    format_balance,
    generate_salt,
    hash_password,
    parse_iso,
    validate_amount,
    validate_currency_code,
    validate_password,
    validate_username,
)


class User:
    """Пользователь системы с хешированным паролем и солью."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        self._user_id = user_id
        self._username = validate_username(username)
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создать нового пользователя: проверить пароль, сгенерировать соль."""
        validate_password(password)
        salt = generate_salt()
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hash_password(password, salt),
            salt=salt,
            registration_date=datetime.now().replace(microsecond=0),
        )

    @property
    def user_id(self) -> int:
        """Идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        self._username = validate_username(value)

    @property
    def hashed_password(self) -> str:
        """Хеш пароля."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Соль пароля."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации."""
        return self._registration_date

    def get_user_info(self) -> dict[str, Any]:
        """Информация о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Сменить пароль: новая соль и новый хеш."""
        validate_password(new_password)
        self._salt = generate_salt()
        self._hashed_password = hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """Проверить, совпадает ли пароль с сохранённым хешем."""
        candidate = hash_password(password, self._salt)
        return hmac.compare_digest(candidate, self._hashed_password)

    def to_dict(self) -> dict[str, Any]:
        """Сериализация для users.json."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "User":
        """Восстановить пользователя из записи users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=parse_iso(data["registration_date"]),
        )


class Wallet:
    """Кошелёк пользователя для одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        self.currency_code = validate_currency_code(currency_code)
        self._balance = 0.0
        self.balance = balance

    @property
    def balance(self) -> float:
        """Текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополнить баланс на положительную сумму."""
        value = validate_amount(amount)
        self.balance = round(self._balance + value, BALANCE_PRECISION)

    def withdraw(self, amount: float) -> None:
        """Снять средства, если их достаточно."""
        value = validate_amount(amount)
        if value > self._balance:
            raise InsufficientFundsError(self._balance, value, self.currency_code)
        self.balance = round(self._balance - value, BALANCE_PRECISION)

    def get_balance_info(self) -> str:
        """Строка вида 'BTC: 0.0500'."""
        return (
            f"{self.currency_code}: {format_balance(self.currency_code, self._balance)}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализация кошелька."""
        return {"currency_code": self.currency_code, "balance": self._balance}


class Portfolio:
    """Все кошельки одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ) -> None:
        self._user_id = user_id
        self._wallets: dict[str, Wallet] = dict(wallets) if wallets else {}
        self._user = user

    @property
    def user_id(self) -> int:
        """Идентификатор владельца."""
        return self._user_id

    @property
    def user(self) -> User | None:
        """Владелец портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков."""
        return dict(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавить новый кошелёк; код валюты должен быть уникальным."""
        code = validate_currency_code(currency_code)
        if code in self._wallets:
            raise ValueError(f"Кошелёк '{code}' уже есть в портфеле")
        wallet = Wallet(code)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Кошелёк по коду валюты или None."""
        return self._wallets.get(validate_currency_code(currency_code))

    def get_total_value(
        self,
        base_currency: str = BASE_CURRENCY,
        rates: Mapping[str, float] | None = None,
    ) -> float:
        """Общая стоимость портфеля в базовой валюте.

        rates — словарь курсов к USD ({'BTC_USD': 59300.0, ...});
        если не передан, используются курсы-заглушки.
        """
        base = validate_currency_code(base_currency)
        pairs = STUB_RATES_TO_USD if rates is None else rates
        total = 0.0
        for code, wallet in self._wallets.items():
            rate = convert_rate(code, base, pairs)
            if rate is None:
                raise ApiRequestError(f"нет курса {code}→{base}")
            total += wallet.balance * rate
        return total

    def to_dict(self) -> dict[str, Any]:
        """Сериализация для portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], user: User | None = None
    ) -> "Portfolio":
        """Восстановить портфель из записи portfolios.json."""
        wallets = {
            code: Wallet(code, float(info.get("balance", 0.0)))
            for code, info in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets, user=user)
