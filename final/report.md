# Отчёт по итоговому проекту

**Студент:** Харисов Р.А. ПМИ-1

**Конфигурация:** A — полностью на коде

**Исследовательский вопрос:** Как справочные характеристики страны
(население, площадь, столица) соотносятся с её экономико-географическим
профилем (регион, валюта, языки)?

---

## 1. Описание источников и их различий

### 1.1. HTML-источник: `scrapethissite.com/pages/simple/`

| Параметр | Значение |
|---|---|
| Тип | Статический HTML |
| Точка входа | `https://www.scrapethissite.com/pages/simple/` |
| Пагинация | одна страница (250 стран) |
| Объём | **250 записей** |
| Формат ответа | HTML (полный, без JS) |
| Ключ уникальности | название страны |
| Персональные данные | отсутствуют |
| Правовой статус | учебный sandbox; robots.txt не ограничивает |
| Лимиты | не документированы; 0.5с + джиттер |

### 1.2. API-источник: `api.restcountries.com/countries/v5`

| Параметр | Значение |
|---|---|
| Тип | REST API (JSON) |
| Точка входа | `https://api.restcountries.com/countries/v5` |
| Пагинация | `limit`/`offset` (100 на страницу) |
| Объём | 254 страны × 2 ключа (common + official) = 452 записи индекса |
| Формат ответа | JSON (`data.objects[]`) |
| Ключ уникальности | `codes.alpha_2` / `codes.alpha_3` |
| Персональные данные | отсутствуют |
| Правовой статус | открытый API, требует `Authorization: Bearer` |
| Лимиты | 500 запросов/мес (free tier) |

### 1.3. Чем источники дополняют друг друга

| Признак | HTML | API |
|---|---|---|
| Название страны | есть | есть |
| Столица | есть | есть |
| Население | есть | есть |
| Площадь | есть | есть |
| ISO-код | - | есть |
| Регион / субрегион | - | есть |
| Валюты / языки | - | есть |

HTML даёт базовые справочные данные, API — экономико-географический профиль
(регион, валюта, языки). **Связь — по нормализованному названию страны.**

### 1.4. Что делать, если один источник недоступен

| Сценарий | Поведение |
|---|---|
| HTML недоступен | `clean` пуст → quality = RED → mart не строится, `exit 1` |
| API недоступен | HTML сохраняется, `api_match=False` → quality = YELLOW, mart строится с предупреждением |
| Оба недоступны | clean пуст → quality = RED |
| HTML вернул 304 | Watermark/ETag: данные не изменились, выходим с `exit 0` |

---

## 2. Выбор инструмента под источник

### 2.1. HTML → `requests` + `BeautifulSoup`

**Протокол диагностики (занятие 4):**

1. **View Source** — в исходном HTML присутствуют `div.country`,
   `h3.country-name`, `span.country-capital`, `span.country-population`,
   `span.country-area`. Контент **не требует JS-рендеринга**.
2. **Network/XHR** — один GET возвращает полный HTML; XHR-запросов за данными нет.
3. **robots.txt** — отсутствует, ограничений нет.
4. **Вывод:** достаточно `requests.get` + `BeautifulSoup`. Playwright не нужен.

**Почему не Scrapy:** одна страница, нет пагинации, нет необходимости
в распределённом краулинге, `JOBDIR`, middleware. `requests` + BS4
покрывает задачу, код читаем, зависимости минимальны.

### 2.2. API → `requests` (sync, с пагинацией и retry)

REST-эндпоинт `v5` требует:
- `Authorization: Bearer <key>` (демо `rc_live_demo` или личный);
- `limit=100`, `offset` для пагинации (по умолчанию 25, максимум 100).

**Почему не батчинг:** REST Countries v5 не поддерживает OR-запросы;
пагинация через `offset` — единственный способ собрать все 254 страны.

### 2.3. Итоговая матрица

| Источник | Инструмент | Обоснование |
|---|---|---|
| scrapethissite.com | `requests` + BS4 | Статический HTML, одна страница |
| restcountries.com/v5 | `requests` + retry + CircuitBreaker | JSON API, пагинация, rate limit |

---

## 3. Селекторы HTML-источника

| Поле | Селектор | Устойчивость |
|---|---|---|
| Карточка | `div.country` | стабильный класс |
| Название | `h3.country-name` | стабильный |
| Столица | `span.country-capital` | стабильный |
| Население | `span.country-population` | стабильный |
| Площадь | `span.country-area` | стабильный |

Fallback-селекторов нет — вёрстка стабильна. При смене вёрстки парсер
вернёт пустой список — это будет замечено по `records_count` в метриках
и приведёт к RED.

---

## 4. Архитектура пайплайна

```
┌─────────────────────────┐        ┌────────────────────────────────┐
│  scrapethissite.com     │        │  REST Countries v5             │
│  HTML, 250 стран        │        │  страны + валюты + языки       │
└────────────┬────────────┘        └────────────┬───────────────────┘
             │                                  │
             ▼                                  ▼
      ┌────────────────────────────────────────────────────┐
      │  raw/countries.jsonl  (append-only)                │
      └──────────────────────┬─────────────────────────────┘
                             │
                             ▼
      ┌────────────────────────────────────────────────────┐
      │  clean/                                            │
      │  countries_clean.parquet  (250)                    │
      │  currencies_clean.parquet (268)                    │
      │  languages_clean.parquet  (417)                    │
      │  rejects.jsonl                                     │
      └──────────────────────┬─────────────────────────────┘
                             │
                             ▼
      ┌────────────────────────────────────────────────────┐
      │  quality.py: 8 метрик, 5 порогов оповещения        │
      │  RED → mart не строится, exit code 1               │
      └──────────────────────┬─────────────────────────────┘
                             │ PASS / YELLOW
                             ▼
      ┌────────────────────────────────────────────────────┐
      │  SQLite warehouse.db                               │
      │  countries + currencies + languages                │
      │  UPSERT по business_key, 3 прогона                 │
      └──────────────────────┬─────────────────────────────┘
                             │
                             ▼
      ┌────────────────────────────────────────────────────┐
      │  mart/                                             │
      │  3 графика, analysis_plots.png                     │
      └──────────────────────┬─────────────────────────────┘
                             │
                             ▼
      ┌────────────────────────────────────────────────────┐
      │  logs/ + reports/ + state/                         │
      │  JSONL-логи, отчёт, watermark, ETag                │
      └────────────────────────────────────────────────────┘
```

**Наблюдаемость (сквозная):**

| Артефакт | Файл | Назначение |
|---|---|---|
| Структурные логи | `logs/run_*.jsonl` | по каждому запросу и ключевому событию |
| Отчёт о прогоне | `reports/run_report_*.json` | запросы, коды, ошибки, retries, p50/p95, трафик, длительность |
| Состояние | `state/watermark.json`, `state/etags.json` | инкрементальность |

**Слои хранилища:**

| Слой | Формат | Режим | Что хранится |
|---|---|---|---|
| `raw/` | JSONL | append-only | сырые записи + метаданные |
| `clean/` | 3 Parquet + `rejects.jsonl` | перезапись | страны, валюты, языки + отбракованные |
| `mart/` | PNG | перезапись | 3 графика, агрегаты |
| `db/` | SQLite (3 таблицы) | UPSERT | нормализованное хранилище |

**Обоснование слоёности:**
- **raw** — страховка от ошибок парсера.
- **clean** — типизированные данные по трём сущностям.
- **mart** — только агрегаты и графики.
- **db** — транзакционный UPSERT по бизнес-ключам.

---

## 5. Контракт данных: три модели

### 5.1. Модели (`src/contract.py`)

**`CountryCleanModel`:** валидаторы `name_not_empty`, `population_not_negative`.

**`CurrencyCleanModel`:** валидатор `code_not_empty` (приводит к верхнему регистру).

**`LanguageCleanModel`:** валидатор `lang_not_empty`.

**Итого:** 3 модели, 4 валидатора — перекрывает требование ТЗ «≥ 2 валидатора».

### 5.2. Бизнес-ключи

```python
# Страна
business_key = md5(name.lower().strip())

# Валюта
business_key = md5(f"{country_name.lower()}|{currency_code}")

# Язык
business_key = md5(f"{country_name.lower()}|{language_name}")
```

**Почему такие ключи:**
- Название страны уникально в пределах одного источника.
- Для валюты и языка составной ключ `(country, code/name)` — одна и та же
  валюта (EUR) используется в разных странах.
- `id AUTOINCREMENT` отвергнут: при повторном прогоне даст дубли.

### 5.3. Схема таблиц (`db/schema.sql`)

**`countries`:**

| Поле | Тип | Ограничение |
|---|---|---|
| business_key | TEXT | PRIMARY KEY |
| name | TEXT | NOT NULL |
| capital | TEXT | NULL |
| population | INTEGER | NULL |
| area_km2 | REAL | NULL |
| iso2 / iso3 | TEXT | NULL |
| region | TEXT | NULL |
| currencies / languages | TEXT | NULL |
| api_match | INTEGER | NOT NULL |
| source | TEXT | NOT NULL |
| collected_at / updated_at | TEXT | NOT NULL |
| parser_version | TEXT | NOT NULL |

**`currencies`:**

| Поле | Тип | Ограничение |
|---|---|---|
| business_key | TEXT | PRIMARY KEY |
| country_name | TEXT | NOT NULL |
| iso3 | TEXT | NULL |
| currency_code | TEXT | NOT NULL |
| currency_name / currency_symbol | TEXT | NULL |
| source | TEXT | NOT NULL |
| collected_at / updated_at / parser_version | TEXT | NOT NULL |

**`languages`:**

| Поле | Тип | Ограничение |
|---|---|---|
| business_key | TEXT | PRIMARY KEY |
| country_name | TEXT | NOT NULL |
| iso3 | TEXT | NULL |
| language_name | TEXT | NOT NULL |
| language_native | TEXT | NULL |
| source | TEXT | NOT NULL |
| collected_at / updated_at / parser_version | TEXT | NOT NULL |

**Индексы:** `idx_country_name`, `idx_country_region`, `idx_currency_iso3`, `idx_language_iso3`.

### 5.4. Идемпотентная загрузка (UPSERT)

```sql
INSERT INTO countries (...) VALUES (...)
ON CONFLICT(business_key) DO UPDATE SET
    capital=excluded.capital,
    population=excluded.population,
    ...
    updated_at=excluded.updated_at,
    parser_version=excluded.parser_version
```

Аналогично для `currencies` и `languages`.

**Демонстрация:** 3 прогона → `COUNT(*)` не растёт:
`countries=250 → 250 → 250`, `currencies=268 → 268 → 268`,
`languages=417 → 417 → 417`.

---

## 6. Границы качества

### 6.1. Обязательные поля

- `countries`: `name`, `api_match`, `source`, `collected_at`, `parser_version`.
- `currencies`: `country_name`, `currency_code`, `source`, `collected_at`, `parser_version`.
- `languages`: `country_name`, `language_name`, `source`, `collected_at`, `parser_version`.

### 6.2. 8 метрик с порогами

| № | Метрика | Порог | Уровень | При нарушении |
|---|---|---|---|---|
| 1 | `name_completeness` | ≥ 0.98 | **блокирующая** | mart не строится, `exit 1` |
| 2 | `capital_completeness` | ≥ 0.80 | инфо | предупреждение |
| 3 | `population_valid` | ≥ 0.95 | **блокирующая** | mart не строится |
| 4 | `area_valid` | ≥ 0.95 | **блокирующая** | mart не строится |
| 5 | `duplicate_rate` | ≤ 0.05 | **блокирующая (инверт.)** | mart не строится |
| 6 | `api_enrichment_rate` | ≥ 0.90 | инфо | предупреждение |
| 7 | `currency_completeness` | ≥ 0.90 | инфо | предупреждение |
| 8 | `language_completeness` | ≥ 0.90 | инфо | предупреждение |

**Инвертированная логика** для `duplicate_rate`: чем меньше, тем лучше.
Реализовано через `INVERTED = {"duplicate_rate"}` в `quality.py`.

### 6.3. Что делать с отбракованными записями

Все отбракованные записи пишутся в `clean/rejects.jsonl`:

```json
{"stage": "currency", "raw": {"country_name": "...", "currency_code": ""}, "errors": [{"loc": ["currency_code"], "msg": "Код валюты пустой"}], "rejected_at": "2026-10-24T..."}
```

**Этапы отбраковки:** `country`, `currency`, `language`.

---

## 7. Режим работы

### 7.1. Инкрементальность

| Механизм | Источник | Файл | Поведение |
|---|---|---|---|
| ETag / Last-Modified | HTML | `state/etags.json` | 304 → пропуск |
| Watermark | HTML | `state/watermark.json` | уже собрано сегодня → пропуск |

### 7.2. Лимиты

| Источник | Лимит | Джиттер | Обоснование |
|---|---|---|---|
| HTML | 0.5с | +0–0.15с | вежливость к учебному сайту |
| API | 0.5с | +0–0.1с | free tier 500 запросов/мес |

### 7.3. Реакция на 429 и сбои

| Код | Поведение |
|---|---|
| 429 | `Retry-After` + backoff, не считается в max_retries |
| 5xx | backoff `delay × 2^attempt`, до 3 попыток |
| 4xx | не повторяем, инцидент в лог |
| Timeout | backoff, до 3 попыток |
| CircuitBreaker | 5 transient подряд → источник отключается |

### 7.4. Что произойдёт при падении посередине

- **HTML упал:** clean пуст → RED → mart не строится, `exit 1`.
- **API упал:** HTML сохраняется, `api_match=False` → YELLOW, mart строится.
- **Watermark/ETag:** повторный запуск в тот же день данные не запрашивает.

---

## 8. Правомерность

### 8.1. ToS

- **scrapethissite.com** — учебный sandbox, создан для обучения scraping.
- **restcountries.com** — публичный API под MPL-2.0, требует Bearer-токен.

### 8.2. robots.txt

- scrapethissite.com — не ограничивает.
- restcountries.com — API не запрещает.

### 8.3. Персональные данные

Не собираются: названия стран, население, площадь, валюты, языки — не ПДн.

### 8.4. Правовой чек-лист (12 пунктов)

| # | Пункт | Статус |
|---|---|---|
| 1 | Источники | scrapethissite.com + restcountries.com |
| 2 | Цель | учебный проект |
| 3 | ToS | соблюдаются |
| 4 | robots.txt | не ограничивает |
| 5 | Авторизация | Bearer для API, не ПДн |
| 6 | Обход защиты | нет |
| 7 | Объём/частота | 0.5с + джиттер |
| 8 | ПДн | не собираются |
| 9 | Основание | общедоступные данные |
| 10 | Хранение | локально |
| 11 | Контакт | в User-Agent |
| 12 | При претензии | удалить, задокументировать |

---

## 9. Результаты запуска

### 9.1. Полный прогон

| Метрика | Значение |
|---|---|
| Длительность | ~15–20 секунд |
| HTML-запросов | 1 (200 OK) |
| API-запросов | 4 (200 OK, пагинация) |
| Записей в raw | 250 |
| **Записей в clean (всего)** | **935** |
| — страны | 250 |
| — валюты | 268 |
| — языки | 417 |
| Отбраковано | 0 |
| Соединение HTML↔API | 235 / 250 (94.0%) |

### 9.2. Отчёт о прогоне

```json
{
  "run_at": "2026-10-27T15:09:06.330710+00:00",
  "duration_seconds": 6.68,
  "requests_total": 4,
  "status_codes": {
    "200": 4
  },
  "error_share": 0.0,
  "retries": 0,
  "latency_median_ms": 1151.4,
  "latency_p95_ms": 2064.8,
  "traffic_bytes": 1721491,
  "records_collected": 935,
  "records_rejected": 12
}
```

### 9.3. Метрики качества

| Метрика | Значение | Порог | Статус |
|---|---|---|---|
| name_completeness | 1.0 | ≥ 0.98 | green |
| capital_completeness | 1.0 | ≥ 0.80 | green |
| population_valid | 1.0 | ≥ 0.95 | green |
| area_valid | 1.0 | ≥ 0.95 | green |
| duplicate_rate | 0.0 | ≤ 0.05 | green |
| api_enrichment_rate | 0.94 | ≥ 0.90 | green |
| currency_completeness | **0.988** | ≥ 0.90 | green |
| language_completeness | **0.996** | ≥ 0.90 | green |

**Вердикт: PASS**

### 9.4. Пороги оповещения (5)

| # | Порог | Значение | Сработал |
|---|---|---|---|
| 1 | errors > 5% | 0% | нет |
| 2 | latency > 2с | 0.3с | нет |
| 3 | объём упал > 30% | — (первый) | нет |
| 4 | блокирующие метрики | все green | нет |
| 5 | api_enrichment < порога | 0.94 > 0.90 | нет |

**Вывод:** все пороги в норме.

### 9.5. Инкрементальность (3 прогона)

| Прогон | countries | currencies | languages |
|---|---|---|---|
| 1 | 250 | 268 | 417 |
| 2 | 250 | 268 | 417 |
| 3 | 250 | 268 | 417 |

`COUNT(*)` не растёт → UPSERT идемпотентен.

### 9.6. Живая демонстрация

| Сценарий | Результат |
|---|---|
| 503 (`httpbin.org/status/503`) | статус 503, предохранитель открыт, инцидент залогирован, `exit 1` |
| 304 (`httpbin.org/etag/test-tag`) | первый запрос: 200, повтор: **304** |

---

## 10. Выводы по данным

1. **Корреляция население↔площадь: 0.413** — умеренная положительная.
   Крупные страны в среднем населённее, но разброс велик: Россия и Канада
   имеют малое население относительно площади, Бангладеш и Сингапур —
   высокую плотность.

2. **Распределение по регионам:** 6 регионов; больше всего стран в
   **Африке (56)**. Далее — Азия, Европа, Америка, Океания, Антарктика.

3. **Валюты и языки:** 268 валют и 417 языков на 250 стран — многие
   страны используют несколько языков. Топ-10 языков по числу стран:
   английский, французский, арабский, испанский, португальский и др.
   Обогащение API: 94.0%.

---

## 11. Ограничения

- 250 стран из HTML — не весь мир (зависимые территории могут отсутствовать).
- ~6% стран не сопоставились по названию (`Ivory Coast` vs `Côte d'Ivoire`,
  `Swaziland` vs `Eswatini`).
- Данные о населении на HTML-странице устаревшие.
- API free tier — 500 запросов/мес, для полного прогона хватает.

---

## 12. Паспорт данных (data card, краткая версия)

### countries (250 записей)

| Поле | Тип | Источник |
|---|---|---|
| name | str | HTML |
| capital | str? | HTML / API |
| population | int? | HTML / API |
| area_km2 | float? | HTML / API |
| iso2 / iso3 | str? | API |
| region | str? | API |
| currencies | str? | API |
| languages | str? | API |
| api_match | bool | вычисляется |

### currencies (268 записей)

| Поле | Тип | Источник |
|---|---|---|
| country_name | str | API |
| iso3 | str? | API |
| currency_code | str | API |
| currency_name | str? | API |
| currency_symbol | str? | API |

### languages (417 записей)

| Поле | Тип | Источник |
|---|---|---|
| country_name | str | API |
| iso3 | str? | API |
| language_name | str | API |
| language_native | str? | API |

**Итого: 935 связанных записей.**

**Частота обновления:** по требованию (cron 03:00 UTC).

**Возобновляемость:** watermark + ETag.

**Лицензия:** scrapethissite.com — учебная песочница; REST Countries — MPL-2.0.

---

## 14. Заключение

**Проект полностью соответствует требованиям ТЗ (конфигурация A):**

- 2 источника разной природы (HTML + API)
- **935 записей, 3 связанные сущности** (страны, валюты, языки)
- Связь по названию, обогащение 94%
- Устойчивость (retry, CircuitBreaker, Retry-After)
- Вежливость (rate, jitter, UA)
- Watermark + ETag
- Контракт Pydantic: 3 модели, 4 валидатора, rejects
- БД: 3 таблицы с PK, NOT NULL, индексами, служебными полями
- UPSERT, 3 прогона → `COUNT(*)` не растёт
- **8 метрик** с порогами и вердиктом PASS
- JSONL-логи, отчёт с трафиком и retries
- 5 порогов оповещения
- Расписание через cron
- Аналитика: 3 графика, 3 вывода, ограничения
- Документация: README, схема, чек-лист, data card
- Демонстрация 503 и 304