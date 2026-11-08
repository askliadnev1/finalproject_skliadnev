# ValutaTrade Hub

Консольная платформа для отслеживания и симуляции торговли фиатными и криптовалютами.
Пользователь регистрируется, пополняет виртуальный USD-счёт, покупает и продаёт валюты
по актуальным курсам, смотрит портфель и курсы.

Система состоит из двух сервисов:
- **Core Service** — CLI, пользователи, портфели, сделки (`valutatrade_hub/core`, `cli`);
- **Parser Service** — получение курсов из CoinGecko (крипто) и ExchangeRate-API (фиат),
  кеш `data/rates.json` и история `data/exchange_rates.json` (`valutatrade_hub/parser_service`).

## Структура проекта

```
finalproject_skliadnev_m26-555/
├── data/
│   ├── users.json            # пользователи (хеш пароля + соль)
│   ├── portfolios.json       # портфели и кошельки
│   ├── rates.json            # кеш актуальных курсов (Core читает его)
│   └── exchange_rates.json   # история измерений Parser Service
├── valutatrade_hub/
│   ├── logging_config.py     # логи: формат, уровень, ротация
│   ├── decorators.py         # @log_action для BUY/SELL/REGISTER/LOGIN
│   ├── core/
│   │   ├── currencies.py     # Currency, FiatCurrency, CryptoCurrency, get_currency()
│   │   ├── exceptions.py     # доменные исключения
│   │   ├── models.py         # User, Wallet, Portfolio
│   │   ├── usecases.py       # бизнес-логика
│   │   └── utils.py          # валидация, хеширование, конвертация
│   ├── infra/
│   │   ├── settings.py       # Singleton SettingsLoader
│   │   └── database.py       # Singleton DatabaseManager (JSON, атомарная запись)
│   ├── parser_service/
│   │   ├── config.py         # ParserConfig: ключи, URL, валюты, таймауты
│   │   ├── api_clients.py    # BaseApiClient, CoinGeckoClient, ExchangeRateApiClient
│   │   ├── updater.py        # RatesUpdater.run_update()
│   │   ├── storage.py        # запись rates.json и exchange_rates.json
│   │   └── scheduler.py      # периодическое обновление
│   └── cli/
│       └── interface.py      # интерактивный CLI
├── main.py
├── Makefile
├── pyproject.toml
└── uv.lock
```

## Установка

Требуется Python 3.12+ и [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/askliadnev1/finalproject_skliadnev_m26-555.git
cd finalproject_skliadnev_m26-555
make install
```

## API-ключ (Parser Service)

1. Получите бесплатный ключ на https://www.exchangerate-api.com/.
2. Создайте в корне проекта файл `.env` (по образцу `.env.example`):
   ```
   EXCHANGERATE_API_KEY=ваш_ключ
   ```
   Файл `.env` добавлен в `.gitignore` и не попадает в репозиторий.
   Можно задать ключ и обычной переменной окружения `EXCHANGERATE_API_KEY`.

CoinGecko работает без ключа.

## Запуск

```bash
make project      # интерактивная консоль
make lint         # проверка ruff
make build        # сборка пакета
make package-install
```

## Команды CLI

| Команда | Пример |
|--