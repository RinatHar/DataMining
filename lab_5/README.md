# Lab 5 — вариант 6: books.toscrape.com + quotes.toscrape.com

Два паука в одном Scrapy-проекте, общий Item Pipeline, общая БД SQLite
с двумя таблицами (`books`, `quotes`).

## Установка

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

## Обычный прогон

```bash
scrapy crawl books
scrapy crawl quotes
```

## JOBDIR — демонстрация возобновляемости

```bash
scrapy crawl books  -s JOBDIR=jobstate/books_run1
scrapy crawl quotes -s JOBDIR=jobstate/quotes_run1
```

Прервать (Ctrl+C или CLOSESPIDER_ITEMCOUNT), затем повторить ту же команду —
в логе будет `dupefilter/filtered > 0`, т.е. посещённые URL не обходятся заново.

## HTTP-кэш для отладки

```bash
scrapy crawl books  -s HTTPCACHE_ENABLED=True
scrapy crawl quotes -s HTTPCACHE_ENABLED=True
```

Второй прогон подряд даст `httpcache/hit > 0` и заметно меньшее время.

## Проверка деградации

```bash
python quality/smoke_check.py
```

## n8n (no-code эквивалент на подмножестве)

```bash
docker run -it --rm --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v $(pwd)/nocode:/files \
  -e N8N_RESTRICT_FILE_ACCESS_TO=/files \
  docker.n8n.io/n8nio/n8n
```

Импортировать `nocode/workflow.json`, запустить вручную, результат —
`nocode/nocode_result.csv`.

## Воспроизведение с нуля

1. `pip install -r requirements.txt`
2. `scrapy crawl books && scrapy crawl quotes`
3. `python quality/smoke_check.py`
4. Открыть `quality/quality_report.ipynb` для анализа.