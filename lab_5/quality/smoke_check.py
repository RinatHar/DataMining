"""Smoke-check: сравнивает текущий прогон с предыдущим.

Предупреждает, если:
- число записей в books или quotes упало > 20%;
- доля пустых обязательных полей в любой таблице > 5%.
"""

import json
import os
import sqlite3

DB_PATH = "data/crawl.db"
SUMMARY_PATH = "data/quality_summary.json"


def _get_summary():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM books")
    books_total = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*) FROM books
        WHERE upc IS NULL OR upc = ''
           OR title IS NULL OR title = ''
           OR price_excl_tax IS NULL
           OR availability IS NULL
           OR category IS NULL OR category = ''
        """
    )
    books_empty = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM quotes")
    quotes_total = cur.fetchone()[0]
    cur.execute(
        """
        SELECT COUNT(*) FROM quotes
        WHERE quote IS NULL OR quote = ''
           OR author IS NULL OR author = ''
           OR source_tag IS NULL OR source_tag = ''
           OR author_born_date IS NULL OR author_born_date = ''
           OR author_born_place IS NULL OR author_born_place = ''
           OR author_bio IS NULL OR author_bio = ''
        """
    )
    quotes_empty = cur.fetchone()[0]

    conn.close()

    return {
        "books_total": books_total,
        "books_empty_ratio": (books_empty / books_total) if books_total else 0.0,
        "quotes_total": quotes_total,
        "quotes_empty_ratio": (quotes_empty / quotes_total) if quotes_total else 0.0,
    }


def _warn(msg):
    print(f"WARNING: {msg}")


def main():
    current = _get_summary()
    print("Current summary:", current)

    if not os.path.exists(SUMMARY_PATH):
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print("First run: saved baseline.")
        return

    with open(SUMMARY_PATH, encoding="utf-8") as f:
        previous = json.load(f)

    for key_total, key_ratio in [
        ("books_total", "books_empty_ratio"),
        ("quotes_total", "quotes_empty_ratio"),
    ]:
        prev = previous.get(key_total, 0)
        cur_val = current[key_total]
        if prev and cur_val < prev * 0.8:
            _warn(
                f"{key_total} dropped by >20%: {prev} -> {cur_val}"
            )
        if current[key_ratio] > 0.05:
            _warn(
                f"{key_ratio} = {current[key_ratio]:.2%} (> 5%)"
            )

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()