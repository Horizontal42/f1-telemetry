[English](README.md)

# F1 Telemetry Analyzer

Превращает сырую телеметрию круга F1 22 в компактные Markdown-отчёты для анализа через LLM. Сырой круг — около 1М токенов; отчёты — 1–35k.

```bash
# из папки tool/
python -m telemetry technique "races/Zandvoort/Практика/zandvoort_P1_L7_74.074_ferrari.csv"
# -> races/Zandvoort/Практика/reports/zandvoort_P1_L7_74.074_ferrari_technique.md   (~35k токенов)
```

Или просто двойной клик по `run-gui.bat` и кнопка **Generate report**.

## Установка

- Python 3.10+ (только стандартная библиотека — без `pip install`).
- Для GUI нужен Tk; он идёт в стандартном установщике Python на Windows/macOS. CLI работает и без него.

Скачай или склонируй репозиторий. Держи CSV-файлы телеметрии в папке на уровень выше `tool/` (см. [структуру папок](#структура-папок)).

## Что умеет

Пять режимов. Четыре строят отчёты, один переименовывает файлы.

| Режим | Вход | Для анализа |
|-------|------|-------------|
| `technique` | один круг | **как** едешь — точки торможения, скорости в апексах, работа газом, блокировки, расход ресурсов |
| `setup` | один круг | **что** настроено — баланс (US/OS), температуры шин, тормоза, rake и крен подвески |
| `compare` | два+ круга | **где** один круг быстрее — дельта по поворотам и накопленная |
| `race` | папка кругов | вся гонка — темп, деградация в стинтах, износ резины, ERS по кругам |
| `rename` | файлы/папка | вставить тип сессии и номер круга в имя файла (`..._74.074_...` → `..._P1_L7_74.074_...`) |

Отчёты содержат легенду с пояснением каждой колонки, а промпт анализа добавляется в конец файла автоматически — достаточно скинуть файл в LLM. Промпты доступны на RU и EN; выбирается флагом `--lang en` в CLI или переключателем языка в GUI.

### Структура папок

```
Telemetry/
  races/
    Zandvoort/
      Практика/                        <- CSV-файлы после переименования
        zandvoort_P1_L7_74.074_ferrari.csv
        reports/                       <- отчёты technique/setup/compare
      Квалификация/
        zandvoort_Q1_L3_74.897_ferrari.csv
        reports/
      Гонка/
        zandvoort_R_L7_74.152_ferrari.csv
        reports/
          Гонка_race.md                <- отчёт режима race
  tool/                                <- этот репозиторий
    telemetry/
    prompts/
    run-gui.bat
```

## Полезное

**GUI** — двойной клик по `run-gui.bat` (или `run-gui.pyw` без окна консоли, либо `python -m telemetry gui`). Выбери режим и язык промпта (RU/EN), укажи файл/папку, нажми Generate. Диалог открывается в последней использованной папке для каждого режима отдельно. Кнопка **Rename unprocessed** добавляет тип сессии и номер круга к файлам, у которых их ещё нет, и не трогает остальные.

**CLI** — из папки `tool/`:

```bash
python -m telemetry technique races/Zandvoort/Практика/lap.csv
python -m telemetry setup     races/Zandvoort/Практика/lap.csv
python -m telemetry compare   races/Zandvoort/Практика/lap_a.csv races/Zandvoort/Практика/lap_b.csv
python -m telemetry race      races/Zandvoort/Гонка
python -m telemetry rename    races/Zandvoort/Практика   # или отдельные файлы

# выбор языка промпта (по умолчанию: ru)
python -m telemetry technique races/Zandvoort/Практика/lap.csv --lang en
```

Каждый прогон печатает путь к отчёту и оценку токенов:

```
C:\...\Telemetry\reports\lap_technique.md
~33834 tokens (budget 60k)
```

**Rename трогает только необработанные файлы.** Файл считается обработанным, когда в имени есть оба токена: тип сессии (`P1`, `Q2`, `R`, …) и `L<номер>`. Повторный запуск безопасен.

## Входной формат

Телеметрия F1 22 (UDP), экспортированная в CSV (тестировалось на [F1Laps](https://www.f1laps.com)). UTF-8, ~1800 строк на круг (≈29 Гц), 108 каналов. Один файл = один круг. Для режима `race` сложи все круги гонки в одну папку.

## Для разработчиков

Чистый Python на стандартной библиотеке. Конвейер: `parser` → `segments` (+ `corner_metrics`) → `resample` → `report_*`. См. [ARCHITECTURE.ru.md](ARCHITECTURE.ru.md).

```bash
cd tool
python -m pytest -q        # прогнать тесты
python -m telemetry gui    # запустить GUI
```

Новый режим: добавь `telemetry/report_<mode>.py` с функцией `generate(...) -> (abs_path, tokens)` и одну строку в `telemetry/__main__.py`. Парсер, детекция поворотов, адаптивная трасса и общие блоки отчётов переиспользуются.

## Благодарности

Сделано для разбора личных хотлапов в F1 22. Формат экспорта телеметрии — [F1Laps](https://www.f1laps.com).

## Лицензия

MIT — см. [LICENSE](LICENSE).
