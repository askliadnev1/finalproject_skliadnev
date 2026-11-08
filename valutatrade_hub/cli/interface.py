"""Командный интерфейс ValutaTrade Hub (интерактивная консоль)."""

import argparse
import shlex
from collections.abc import Callable

from prettytable import PrettyTable

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import get_supported_codes
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    AuthenticationError,
    CurrencyNotFoundError,
    ValutaTradeError,
)
from valutatrade_hub.core.utils import BASE_CURRENCY, format_balance, format_money
from valutatrade_hub.logging_config import setup_logging

PROMPT = "> "
EXIT_COMMANDS = ("exit", "quit")
SEPARATOR = "-" * 33
SMALL_RATE_THRESHOLD = 1.0


class CommandError(Exception):
    """Ошибка разбора аргументов команды."""


class _ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser, который не завершает программу при ошибке."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise CommandError(message)


def format_rate(rate: float) -> str:
    """Курс: 2 знака для больших значений, 8 — для маленьких."""
    return f"{rate:.2f}" if rate >= SMALL_RATE_THRESHOLD else f"{rate:.8f}"


def format_timestamp(timestamp: str) -> str:
    """'2025-10-09T10:30:00Z' → '2025-10-09 10:30:00'."""
    return timestamp.replace("T", " ").removesuffix("Z")


def build_parser() -> tuple[
    argparse.ArgumentParser, dict[str, argparse.ArgumentParser]
]:
    """Создать парсер команд и словарь подпарсеров для справки."""
    parser = _ArgumentParser(prog="valutatrade", add_help=False)
    subparsers = parser.add_subparsers(dest="command")
    commands: dict[str, argparse.ArgumentParser] = {}

    def add(name: str, description: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, description=description)
        commands[name] = sub
        return sub

    register = add("register", "Регистрация нового пользователя")
    register.add_argument("--username", required=True, help="имя пользователя")
    register.add_argument("--password", required=True, help="пароль (от 4 символов)")

    login = add("login", "Вход в систему")
    login.add_argument("--username", required=True, help="имя пользователя")
    login.add_argument("--password", required=True, help="пароль")

    add("logout", "Выход из аккаунта")

    show = add("show-portfolio", "Показать портфель и итоговую стоимость")
    show.add_argument("--base", default=None, help="базовая валюта (по умолчанию USD)")

    for name, description in (("buy", "Купить валюту"), ("sell", "Продать валюту")):
        trade = add(name, description)
        trade.add_argument("--currency", required=True, help="код валюты, например BTC")
        trade.add_argument("--amount", required=True, help="количество валюты")

    rate = add("get-rate", "Курс одной валюты к другой")
    rate.add_argument("--from", dest="from_code", required=True, help="исходная валюта")
    rate.add_argument("--to", dest="to_code", required=True, help="целевая валюта")

    update = add("update-rates", "Обновить курсы из внешних API")
    update.add_argument(
        "--source",
        default=None,
        choices=("coingecko", "exchangerate"),
        help="только один источник",
    )

    show_rates = add("show-rates", "Курсы из локального кеша")
    show_rates.add_argument("--currency", default=None, help="одна валюта")
    show_rates.add_argument("--top", type=int, default=None, help="N дорогих крипто")
    show_rates.add_argument("--base", default=None, help="базовая валюта")

    return parser, commands


class ValutaTradeCLI:
    """Интерактивная консоль: разбор команд и вывод результатов."""

    def __init__(self) -> None:
        self._parser, self._commands = build_parser()
        self._session: dict | None = None
        self._handlers: dict[str, Callable[[argparse.Namespace], None]] = {
            "register": self._register,
            "login": self._login,
            "logout": self._logout,
            "show-portfolio": self._show_portfolio,
            "buy": self._buy,
            "sell": self._sell,
            "get-rate": self._get_rate,
            "update-rates": self._update_rates,
            "show-rates": self._show_rates,
        }

    def run(self) -> None:
        """Главный цикл: читать команды до exit."""
        print("Добро пожаловать в ValutaTrade Hub!")
        print("Введите help для списка команд, exit — для выхода.")
        while True:
            try:
                line = input(PROMPT)
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.strip() and not self.execute(line):
                break

    def execute(self, line: str) -> bool:
        """Выполнить одну команду. Вернуть False, если нужно выйти."""
        try:
            tokens = shlex.split(line)
        except ValueError as error:
            print(f"Ошибка разбора команды: {error}")
            return True

        command = tokens[0]
        if command in EXIT_COMMANDS:
            print("До свидания!")
            return False
        if command == "help":
            self._print_help(tokens[1:])
            return True

        handler = self._handlers.get(command)
        if handler is None:
            print(f"Неизвестная команда '{command}'. Введите help для списка команд.")
            return True

        try:
            args = self._parser.parse_args(tokens)
        except CommandError as error:
            print(f"Ошибка в аргументах: {error}. Справка: help {command}")
            return True
        except SystemExit:
            return True

        try:
            handler(args)
        except (ValutaTradeError, ValueError, TypeError) as error:
            self._print_error(error, command)
        except Exception as error:
            print(f"Непредвиденная ошибка: {error}")
        return True

    # ---------- служебное ----------

    def _print_help(self, names: list[str]) -> None:
        """Общая справка или справка по одной команде."""
        if names:
            sub = self._commands.get(names[0])
            if sub is None:
                print(f"Неизвестная команда '{names[0]}'")
            else:
                sub.print_help()
            return
        table = PrettyTable(["Команда", "Описание"])
        table.align = "l"
        for name, sub in self._commands.items():
            table.add_row([name, sub.description])
        table.add_row(["help [команда]", "Справка"])
        table.add_row(["exit", "Выход из программы"])
        print(table)
        print("Подробнее о команде: help <команда>")

    @staticmethod
    def _print_error(error: Exception, command: str) -> None:
        """Дружелюбный вывод доменных ошибок."""
        print(error)
        if isinstance(error, CurrencyNotFoundError):
            print(f"Поддерживаемые валюты: {', '.join(get_supported_codes())}")
            print(f"Справка: help {command}")
        elif isinstance(error, ApiRequestError):
            print("Повторите попытку позже или проверьте подключение к сети.")

    def _require_login(self) -> dict:
        """Данные текущей сессии или ошибка, если пользователь не вошёл."""
        if self._session is None:
            raise AuthenticationError("Сначала выполните login")
        return self._session

    @staticmethod
    def _print_changes(changes: list[dict]) -> None:
        """Вывести изменения балансов «было → стало»."""
        print("Изменения в портфеле:")
        for change in changes:
            code = change["currency"]
            before = format_balance(code, change["before"])
            after = format_balance(code, change["after"])
            print(f"- {code}: было {before} → стало {after}")

    # ---------- команды ----------

    def _register(self, args: argparse.Namespace) -> None:
        result = usecases.register(args.username, args.password)
        name = result["username"]
        print(
            f"Пользователь '{name}' зарегистрирован (id={result['user_id']}). "
            f"Войдите: login --username {name} --password ****"
        )

    def _login(self, args: argparse.Namespace) -> None:
        self._session = usecases.login(args.username, args.password)
        print(f"Вы вошли как '{self._session['username']}'")

    def _logout(self, args: argparse.Namespace) -> None:
        if self._session is None:
            print("Вы не вошли в систему")
            return
        print(f"Вы вышли из аккаунта '{self._session['username']}'")
        self._session = None

    def _show_portfolio(self, args: argparse.Namespace) -> None:
        session = self._require_login()
        summary = usecases.get_portfolio_summary(session["user_id"], args.base)
        base = summary["base"]
        if not summary["rows"]:
            print(
                f"Портфель пользователя '{session['username']}' пуст. "
                "Пополните счёт: buy --currency USD --amount 1000"
            )
            return
        print(f"Портфель пользователя '{session['username']}' (база: {base}):")
        for row in summary["rows"]:
            code = row["currency"]
            balance = format_balance(code, row["balance"])
            value = format_balance(base, row["value"])
            print(f"- {code}: {balance}  → {value} {base}")
        print(SEPARATOR)
        print(f"ИТОГО: {format_money(summary['total'])} {base}")

    def _buy(self, args: argparse.Namespace) -> None:
        session = self._require_login()
        result = usecases.buy(session["user_id"], args.currency, args.amount)
        code = result["currency"]
        amount_text = f"{format_balance(code, result['amount'])} {code}"
        if code == BASE_CURRENCY:
            print(f"Пополнение выполнено: {amount_text}")
        else:
            print(
                f"Покупка выполнена: {amount_text} по курсу "
                f"{format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
            )
        self._print_changes(result["changes"])
        if code != BASE_CURRENCY:
            cost = format_money(result["cost"])
            print(f"Оценочная стоимость покупки: {cost} {BASE_CURRENCY}")

    def _sell(self, args: argparse.Namespace) -> None:
        session = self._require_login()
        result = usecases.sell(session["user_id"], args.currency, args.amount)
        code = result["currency"]
        amount_text = f"{format_balance(code, result['amount'])} {code}"
        if code == BASE_CURRENCY:
            print(f"Вывод выполнен: {amount_text}")
        else:
            print(
                f"Продажа выполнена: {amount_text} по курсу "
                f"{format_rate(result['rate'])} {BASE_CURRENCY}/{code}"
            )
        self._print_changes(result["changes"])
        if code != BASE_CURRENCY:
            revenue = format_money(result["revenue"])
            print(f"Оценочная выручка: {revenue} {BASE_CURRENCY}")

    def _get_rate(self, args: argparse.Namespace) -> None:
        result = usecases.get_rate(args.from_code, args.to_code)
        source, target = result["from"], result["to"]
        updated = format_timestamp(result["updated_at"])
        rate = format_rate(result["rate"])
        print(f"Курс {source}→{target}: {rate} (обновлено: {updated})")
        if result["reverse_rate"]:
            reverse = format_rate(result["reverse_rate"])
            print(f"Обратный курс {target}→{source}: {reverse}")
        if result["stale"]:
            print("Внимание: данные устарели. Обновите курсы командой update-rates.")

    def _update_rates(self, args: argparse.Namespace) -> None:
        result = usecases.update_rates(args.source)
        if not result["errors"]:
            print(
                f"Update successful. Total rates updated: {result['updated']}. "
                f"Last refresh: {format_timestamp(result['last_refresh'])}"
            )
        elif result["updated"]:
            print("Update completed with errors. Check logs/parser.log for details.")
        else:
            print("Update failed. Check logs/parser.log for details.")

    def _show_rates(self, args: argparse.Namespace) -> None:
        result = usecases.list_cached_rates(args.currency, args.top, args.base)
        updated = format_timestamp(result["last_refresh"] or "—")
        print(f"Rates from cache (updated at {updated}):")
        for row in result["rows"]:
            print(f"- {row['pair']}: {format_rate(row['rate'])}")


def main() -> None:
    """Точка входа: интерактивная консоль."""
    setup_logging()
    ValutaTradeCLI().run()
