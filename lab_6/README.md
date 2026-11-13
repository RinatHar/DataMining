# Лабораторная работа №6. Вариант 6 (Гибридный набор)

Трёхслойное хранилище (raw → clean → mart) для двух источников:
1. books.toscrape.com (HTML)
2. Open-Meteo API (JSON)

## Запуск (с нуля)
1. Установите зависимости: `pip install -r requirements.txt`
2. Запустите Jupyter Notebook: `jupyter notebook quality_report.ipynb`
3. Выполните все ячейки сверху вниз. Скрипт сам скачает данные, очистит их, загрузит в БД и построит графики.

## Запуск no-code (n8n)
```bash
docker run -it --rm --name n8n -p 5678:5678 ^
  --add-host=host.docker.internal:host-gateway ^
  -v n8n_data:/home/node/.n8n ^
  -v E:\temp\web-scrapers\lb6:/files ^
  -e N8N_RESTRICT_FILE_ACCESS_TO=/files ^
  docker.n8n.io/n8nio/n8n
```
Импортируйте `nocode/lab6.json` в n8n.