# Внешняя торговля Армении: данные Армстата в DuckDB

Сбор, нормализация и документирование данных о внешней торговле Республики Армения из раздела
«External trade database» сайта Статистического комитета РА (Армстат): <https://armstat.am/en/?nid=160>.

Собирается **всё**, что опубликовано в разделе, **на трёх языках** (английский, армянский, русский):

* **веб-база данных** (интерфейс запросов):
  * по странам-партнёрам — годовые данные с 1995 г., месячные с 2003 г. (nid 159 и 717);
  * по 4-значным товарным позициям ТН ВЭД — годовые с 1995 г., месячные с 2007 г. (nid 148);
* **файлы xlsx** по ТН ВЭД ЕАЭС на 2-, 4- и 10-значном уровне за 2018–2025 гг. (nid 766, 777, 778),
  включая скрытые ранние редакции и архивы 7z (в т. ч. документ ТН ВЭД ЕАЭС 2017).

Результат — база данных DuckDB `data/armstat_trade.duckdb` со справочниками на трёх языках,
нормализованными таблицами фактов, полной копией исходных ячеек и выгрузок, проверками качества
и документацией.

## Быстрый старт

```bash
make install   # создаёт .venv и ставит пакет с extras dev + notebook (через uv, если он есть; Python ≥ 3.10)
make all       # catalog → fetch-files → fetch-db → tnved → build → docs  (~40–60 минут, в основном загрузка)
```

Все цели `make` автоматически используют `.venv/bin/python`, если окружение создано (системный
`pip install` в Homebrew/Debian-Python запрещён, PEP 668). Другой интерпретатор: `make build PY=python3`.

Или по шагам (в активированном окружении: `source .venv/bin/activate`):

```bash
python -m armstat_trade catalog       # страницы раздела на en/hy/ru → data/catalog/*.json
python -m armstat_trade fetch-files   # xlsx/7z → data/raw/files (+ распаковка 7z)
python -m armstat_trade fetch-db      # веб-БД через выгрузку Excel → data/raw/db (≈ 380 запросов)
python -m armstat_trade tnved         # русские названия разделов/групп из ТН ВЭД 2017 (нужен textutil или soffice)
python -m armstat_trade build         # → data/armstat_trade.duckdb
python -m armstat_trade docs          # → docs/data_dictionary.md, docs/inventory.md
```

Распаковка 7z требует `7zz`/`7z` (например, `brew install sevenzip`) или пакета `py7zr` (`.venv/bin/python -m pip install '.[7z]'` либо `uv pip install --python .venv/bin/python '.[7z]'`).
Повторный запуск `fetch-db` докачивает только отсутствующее и всегда обновляет два последних года
(`--refresh-last N`), а также перепроверяет уже скачанные выгрузки и перезапрашивает некорректные.

Пример запроса:

```bash
duckdb data/armstat_trade.duckdb -c "
  SELECT year, round(sum(export_kusd)/1e3) AS export_musd, round(sum(import_origin_kusd)/1e3) AS import_musd
  FROM v_db_country_annual GROUP BY year ORDER BY year"
```

## Тетрадка Jupyter с примерами

[`docs/examples.ipynb`](docs/examples.ipynb) — примеры запросов, сравнений источников и графиков. Она хранится
с результатами выполнения, поэтому её можно просто открыть на GitHub. Чтобы работать с ней интерактивно:

1. Установите окружение (создаёт `.venv` с JupyterLab, matplotlib и ядром Python):

   ```bash
   make install
   ```

2. Убедитесь, что база собрана: файл `data/armstat_trade.duckdb` должен существовать
   (в первый раз — `make all`, при уже скачанных данных — `make build`).

3. Запустите JupyterLab с тетрадкой:

   ```bash
   make lab
   ```

   Откроется браузер с тетрадкой (`http://localhost:8888/lab/tree/docs/examples.ipynb`), в панели
   файлов — весь репозиторий. То же без `make`:
   `source .venv/bin/activate && jupyter lab --ServerApp.root_dir=. docs/examples.ipynb`.

4. Проверьте ядро в правом верхнем углу: **Python 3 (ipykernel)** — это ядро из `.venv`
   (`.venv/bin/jupyter kernelspec list` покажет путь внутри `.venv`).

5. Выполните ячейки: **Run → Run All Cells** или по одной — `Shift+Enter`. Первая ячейка находит корень
   репозитория (по `pyproject.toml`) и открывает базу только для чтения, так что Jupyter можно запускать
   из любой папки репозитория.

6. Остановка — `Ctrl+C` в терминале, где запущен `make lab`, и подтверждение `y`.

**VS Code:** откройте `docs/examples.ipynb`, нажмите **Select Kernel → Python Environments** и выберите
`.venv/bin/python` (нужно расширение Jupyter).

Полезно знать:

* Если база открыта **на запись** другим процессом (например, `duckdb data/armstat_trade.duckdb`
  без `-readonly`), тетрадка не сможет к ней подключиться — закройте этот процесс.
* После пересборки базы (`make build`) перезапустите ядро (**Kernel → Restart Kernel**): открытое
  подключение продолжает видеть прежний файл.
* Перед коммитом обновите сохранённые результаты одним чистым прогоном всех ячеек по порядку:
  `make notebook` (без браузера; выполняет тетрадку и записывает результаты в файл).

## Структура репозитория

```
├── README.md                  этот файл
├── Makefile                   команды конвейера
├── pyproject.toml             пакет armstat_trade (CLI: armstat-trade)
├── src/armstat_trade/
│   ├── config.py              пути, страницы раздела, языки, параметры HTTP
│   ├── http.py                HTTP-клиент: повторы, паузы между запросами, сеансы
│   ├── catalog.py             шаг 1: обход страниц на 3 языках, перечень файлов и опций форм
│   ├── fetch_files.py         шаг 2: загрузка файлов, распаковка 7z, sha256
│   ├── fetch_db.py            шаг 3: выгрузка веб-БД (запрос → /excelopen.php → проверка)
│   ├── build.py               шаг 4: разбор и сборка DuckDB
│   ├── docs.py                генерация словаря данных и перечня источников
│   ├── reference.py           статические справочники и словари соответствий
│   ├── cli.py, __main__.py    командная строка
│   └── parsers/
│       ├── pages.py           HTML страниц: ссылки на файлы, опции форм
│       ├── db_export.py       выгрузки веб-БД + проверка их соответствия запросу
│       ├── xlsx_reader.py     быстрый потоковый ридер xlsx (кэшированные значения + формулы)
│       ├── files_hs2.py       бюллетени по 2-значным группам (универсальный разбор шапок таблиц)
│       ├── files_hs4.py       таблицы по 4-значным позициям
│       ├── files_hs10.py      таблицы по 10-значным кодам (иерархия разделов/групп/позиций)
│       ├── tnved.py           заголовки ТН ВЭД 2017 (.doc)
│       └── common.py          очистка значений и кодов
├── sql/
│   ├── schema.sql             таблицы + COMMENT ON (описания хранятся в самой БД)
│   ├── views.sql              представления
│   └── qc.sql                 проверки качества
├── data/
│   ├── catalog/               манифесты (в git): pages.json, files.json, db_queries.json, db_options/
│   ├── interim/               tnved_2017.csv (в git)
│   ├── raw/                   скачанные страницы, файлы, выгрузки (не в git, воспроизводимо)
│   └── armstat_trade.duckdb   результат (не в git)
├── docs/                      документация и тетрадка examples.ipynb
├── scripts/run_notebook.py    выполнение тетрадки с сохранением результатов (make notebook)
└── tests/                     тесты парсеров и собранной БД
```

## Документация

| документ | содержание |
|---|---|
| [docs/sources.md](docs/sources.md) | раздел сайта, страницы, языки, устройство веб-БД и её особенности, единицы и условные обозначения |
| [docs/files.md](docs/files.md) | содержание файлов: листы, колонки, иерархии, особенности |
| [docs/database.md](docs/database.md) | проект БД: принципы, схема (ER), таблицы, представления, примеры запросов |
| [docs/data_dictionary.md](docs/data_dictionary.md) | все таблицы и колонки (генерируется) |
| [docs/inventory.md](docs/inventory.md) | перечень файлов и запросов (генерируется) |
| [docs/data_quality.md](docs/data_quality.md) | проверки качества и найденные проблемы источников |
| [docs/examples.ipynb](docs/examples.ipynb) | тетрадка Jupyter: примеры запросов, сравнений источников и визуализаций (интерактивно — `make lab`, см. раздел выше) |
| [docs/maintenance.md](docs/maintenance.md) | сопровождение: обновление, новые годы, изменения на сайте |

## Основные таблицы

| таблица / представление | что внутри |
|---|---|
| `v_db_country_annual`, `v_db_country_monthly` | торговля по странам (экспорт, импорт по стране происхождения и по стране отправления), тыс. $ |
| `v_db_commodity_annual`, `v_db_commodity_monthly` | торговля по 4-значным позициям ТН ВЭД, т и тыс. $ |
| `v_file_hs10_current` | 10-значные коды: количество, т, $ (2018–2025) |
| `v_file_hs4_current` | 4-значные позиции по основе данных (всего / декларации / физлица) |
| `v_file_hs2_partner_current` | группы ТН ВЭД × страна / группа стран: т, млн драмов, тыс. $ |
| `file_country_trade`, `file_sitc_trade`, `file_bec_trade`, `file_hs2_trade` | многолетние таблицы бюллетеней (все редакции; `v_*_latest` — последняя) |
| `dim_country`, `dim_hs`, `dim_hs_section`, … | справочники с названиями на en / hy / ru |
| `raw_xlsx_cell`, `stg_db_*` | исходные данные без потерь |

## Важно при использовании

* Единицы — как в источнике и указаны в имени колонки (`value_kusd` — тыс. $, `value_usd` — $, …).
* Строки итогов (`row_type = 'total'`, `'chapter'`, `'group'`, …) хранятся вместе с детальными — фильтруйте.
* Файлы — публикации на дату выпуска; веб-БД содержит более поздние уточнения. Для одного года значения
  в разных источниках могут расходиться (см. `qc_file_vs_db_hs4`).
* 2026 год неполный.

## Источник

Данные: Статистический комитет Республики Армения, <https://armstat.am>. Лицензия кода репозитория пока не выбрана.
