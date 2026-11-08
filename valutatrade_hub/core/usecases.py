"""Бизнес-логика: регистрация, вход, покупка, продажа, курсы, портфель."""

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    RateUnavailableError,
    WalletNotFoundError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    BASE_CURRENCY,
    STUB_RATES_TO_USD,
    convert_rate,
    parse_iso,
    validate_amount,
    validate_password,
    validate_username,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

STUB_SOURCE = "Stub"
DEFAULT_TTL_SECONDS = 300

_db = DatabaseManager()
_settings = SettingsLoader()


# ---------- время и свежесть курсов ----------


def utc_now_iso() -> str:
    """Текущее время UTC в формате ISO с суффиксом Z."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _age_seconds(timestamp: str) -> float:
    """Сколько секунд прошло с момента timestamp."""
    moment = parse_iso(timestamp)
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return (datetime.now(UTC) - moment).total_seconds()


def _is_fresh(timestamp: str | None) -> bool:
    """Свежий ли курс с учётом TTL из SettingsLoader."""
    if not timestamp:
        return False
    ttl = _settings.get("rates_ttl_seconds", DEFAULT_TTL_SECONDS)
    return _age_seconds(timestamp) <= ttl


# ---------- пользователи ----------


def _find_user_record(username: str) -> dict | None:
    """Найти запись пользователя по имени."""
    for record in _db.load_users():
        if record["username"] == username:
            return record
    return None


@log_action("REGISTER")
def register(username: str, password: str) -> dict[str, Any]:
    """Зарегистрировать пользователя и создать ему пустой портфель."""
    username = validate_username(username)
    users = _db.load_users()
    if any(record["username"] == username for record in users):
        raise AuthenticationError(f"Имя пользователя '{username}' уже занято")
    validate_password(password)

    user_id = max((record["user_id"] for record in users), default=0) + 1
    user = User.create(user_id, username, password)
    users.append(user.to_dict())
    _db.save_users(users)
    _save_portfolio(Portfolio(user_id=user_id, user=user))
    return {"user_id": user_id, "username": username}


@log_action("LOGIN")
def login(username: str, password: str) -> dict[str, Any]:
    """Проверить имя и пароль, вернуть данные для сессии."""
    username = validate_username(username)
    record = _find_user_record(username)
    if record is None:
        raise AuthenticationError(f"Пользователь '{username}' не найден")
    user = User.from_dict(record)
    if not user.verify_password(password):
        raise AuthenticationError("Неверный пароль")
    return {"user_id": user.user_id, "username": user.username}


# ---------- портфели ----------


def _load_portfolio(user_id: int) -> Portfolio:
    """Загрузить портфель пользователя (или пустой, если записи нет)."""
    for record in _db.load_portfolios():
        if record["user_id"] == user_id:
            return Portfolio.from_dict(record)
    return Portfolio(user_id=user_id)


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохранить портфель: чтение → замена записи → атомарная запись."""
    records = [
        record
        for record in _db.load_portfolios()
        if record["user_id"] != portfolio.user_id
    ]
    records.append(portfolio.to_dict())
    records.sort(key=lambda record: record["user_id"])
    _db.save_portfolios(records)


def _change(code: str, before: float, after: float) -> dict[str, Any]:
    """Описание изменения баланса для отчёта."""
    return {"currency": code, "before": before, "after": after}


# ---------- курсы ----------


def refresh_rates() -> None:
    """Обновить кеш курсов.

    Пока Parser Service не подключён, в кеш пишутся курсы-заглушки.
    """
    timestamp = utc_now_iso()
    cache = _db.load_rates()
    for pair, rate in STUB_RATES_TO_USD.items():
        cache["pairs"][pair] = {
            "rate": rate,
            "updated_at": timestamp,
            "source": STUB_SOURCE,
        }
    cache["last_refresh"] = timestamp
    _db.save_rates(cache)


def _flat_rates(cache: dict) -> dict[str, float]:
    """{'BTC_USD': {...}} → {'BTC_USD': 59300.0}."""
    return {pair: float(info["rate"]) for pair, info in cache["pairs"].items()}


def _lookup_rate(cache: dict, from_code: str, to_code: str) -> tuple[float, str] | None:
    """Найти курс from→to в кеше; вернуть (курс, время самого старого среза)."""
    rate = convert_rate(from_code, to_code, _flat_rates(cache))
    if rate is None:
        return None
    stamps = [
        cache["pairs"][f"{code}_{BASE_CURRENCY}"]["updated_at"]
        for code in (from_code, to_code)
        if code != BASE_CURRENCY
    ]
    return rate, max(stamps, key=_age_seconds)


def _rate_result(
    source: str, target: str, rate: float, updated_at: str, stale: bool
) -> dict[str, Any]:
    """Результат запроса курса."""
    return {
        "from": source,
        "to": target,
        "rate": rate,
        "reverse_rate": 1 / rate if rate else None,
        "updated_at": updated_at,
        "stale": stale,
    }


def get_rate(from_code: str, to_code: str) -> dict[str, Any]:
    """Курс from→to из кеша rates.json с учётом TTL.

    Если кеш устарел — пытаемся обновить. Если обновить не удалось,
    но старые данные есть — возвращаем их с пометкой stale=True.
    """
    source = get_currency(from_code).code
    target = get_currency(to_code).code
    if source == target:
        return _rate_result(source, target, 1.0, utc_now_iso(), stale=False)

    found = _lookup_rate(_db.load_rates(), source, target)
    if found is None or not _is_fresh(found[1]):
        try:
            refresh_rates()
        except ApiRequestError as error:
            if found is None:
                raise RateUnavailableError(source, target) from error
        else:
            found = _lookup_rate(_db.load_rates(), source, target) or found

    if found is None:
        raise RateUnavailableError(source, target)
    rate, updated_at = found
    return _rate_result(source, target, rate, updated_at, not _is_fresh(updated_at))


def _trade_rate(code: str) -> float:
    """Курс валюты к USD для сделки."""
    if code == BASE_CURRENCY:
        return 1.0
    try:
        return get_rate(code, BASE_CURRENCY)["rate"]
    except (RateUnavailableError, ApiRequestError) as error:
        message = f"Не удалось получить курс для {code}→{BASE_CURRENCY}"
        raise RateUnavailableError(code, BASE_CURRENCY, message) from error


def _load_actual_rates() -> dict:
    """Кеш курсов; если устарел — попытка обновить (без ошибки при неудаче)."""
    cache = _db.load_rates()
    if not _is_fresh(cache.get("last_refresh")):
        with suppress(ApiRequestError):
            refresh_rates()
            cache = _db.load_rates()
    return cache


# ---------- сделки ----------


@log_action("BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Купить валюту: списать стоимость с USD-кошелька и зачислить покупку."""
    value = validate_amount(amount)
    code = get_currency(currency_code).code
    rate = _trade_rate(code)
    cost = value * rate
    portfolio = _load_portfolio(user_id)
    changes = []

    if code != BASE_CURRENCY:
        usd_wallet = portfolio.get_wallet(BASE_CURRENCY)
        if usd_wallet is None:
            raise InsufficientFundsError(0.0, cost, BASE_CURRENCY)
        usd_before = usd_wallet.balance
        usd_wallet.withdraw(cost)
        changes.append(_change(BASE_CURRENCY, usd_before, usd_wallet.balance))

    wallet = portfolio.get_wallet(code) or portfolio.add_currency(code)
    before = wallet.balance
    wallet.deposit(value)
    changes.insert(0, _change(code, before, wallet.balance))
    _save_portfolio(portfolio)

    return {
        "currency": code,
        "amount": value,
        "rate": rate,
        "base": BASE_CURRENCY,
        "cost": cost,
        "before": before,
        "after": wallet.balance,
        "changes": changes,
    }


@log_action("SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Продать валюту: списать её и зачислить выручку на USD-кошелёк."""
    value = validate_amount(amount)
    code = get_currency(currency_code).code
    portfolio = _load_portfolio(user_id)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise WalletNotFoundError(code)

    rate = _trade_rate(code)
    revenue = value * rate
    before = wallet.balance
    wallet.withdraw(value)
    changes = [_change(code, before, wallet.balance)]

    if code != BASE_CURRENCY:
        usd_wallet = portfolio.get_wallet(BASE_CURRENCY) or portfolio.add_currency(
            BASE_CURRENCY
        )
        usd_before = usd_wallet.balance
        usd_wallet.deposit(revenue)
        changes.append(_change(BASE_CURRENCY, usd_before, usd_wallet.balance))

    _save_portfolio(portfolio)
    return {
        "currency": code,
        "amount": value,
        "rate": rate,
        "base": BASE_CURRENCY,
        "revenue": revenue,
        "before": before,
        "after": wallet.balance,
        "changes": changes,
    }


# ---------- портфель ----------


def get_portfolio_summary(
    user_id: int, base_currency: str | None = None
) -> dict[str, Any]:
    """Кошельки пользователя и их стоимость в базовой валюте."""
    base_code = base_currency or _settings.get("default_base_currency", BASE_CURRENCY)
    try:
        base = get_currency(base_code).code
    except CurrencyNotFoundError:
        raise ValueError(f"Неизвестная базовая валюта '{base_code}'") from None

    portfolio = _load_portfolio(user_id)
    cache = _load_actual_rates()
    rates = _flat_rates(cache)

    rows = []
    for code, wallet in portfolio.wallets.items():
        rate = convert_rate(code, base, rates)
        if rate is None:
            raise RateUnavailableError(code, base)
        rows.append(
            {
                "currency": code,
                "balance": wallet.balance,
                "value": wallet.balance * rate,
            }
        )

    return {
        "base": base,
        "rows": rows,
        "total": portfolio.get_total_value(base, rates),
        "last_refresh": cache.get("last_refresh"),
    }
