import os
import re
import sqlite3
from datetime import datetime

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


# Валидация
class ValidatePipeline:
    """Валидация обязательных полей для каждой схемы."""

    required_books = [
        "upc", "title", "price_excl_tax", "availability",
        "category", "product_url",
    ]
    required_quotes = [
        "quote", "author", "source_tag",
        "author_born_date", "author_born_place", "author_bio",
    ]

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        source = adapter.get("source")
        required = (
            self.required_books if source == "books" else self.required_quotes
        )
        missing = [f for f in required if not adapter.get(f)]
        if missing:
            spider.crawler.stats.inc_value(
                f"dropped/missing_fields_{source}"
            )
            raise DropItem(f"Missing fields ({source}): {missing}")
        return item


# Очистка / типизация
class CleanPipeline:
    """Типизация и нормализация для обеих схем."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("source") == "books":
            self._clean_book(adapter, spider)
        else:
            self._clean_quote(adapter, spider)
        return item

    # books
    def _clean_book(self, adapter, spider):
        adapter["upc"] = (adapter.get("upc") or "").strip()
        adapter["title"] = " ".join((adapter.get("title") or "").split())
        adapter["category"] = " ".join(
            (adapter.get("category") or "").split()
        ).lower()

        price_raw = adapter.get("price_excl_tax") or ""
        try:
            adapter["price_excl_tax"] = float(
                re.sub(r"[^\d.,]", "", price_raw).replace(",", ".")
            )
        except (ValueError, TypeError):
            spider.crawler.stats.inc_value("dropped/invalid_price")
            raise DropItem(f"Invalid price: {price_raw!r}")

        avail_raw = adapter.get("availability") or ""
        m = re.search(r"(\d+)", avail_raw)
        if not m:
            spider.crawler.stats.inc_value("dropped/invalid_availability")
            raise DropItem(f"Invalid availability: {avail_raw!r}")
        adapter["availability"] = int(m.group(1))

        reviews_raw = adapter.get("reviews")
        try:
            adapter["reviews"] = int(reviews_raw) if reviews_raw else 0
        except (ValueError, TypeError):
            adapter["reviews"] = 0

        rating_raw = adapter.get("rating") or ""
        rating_map = {
            "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
        }
        adapter["rating"] = rating_map.get(rating_raw.strip(), None)

        desc = adapter.get("description") or ""
        adapter["description"] = " ".join(desc.split())

    # quotes
    def _clean_quote(self, adapter, spider):
        adapter["quote"] = " ".join((adapter.get("quote") or "").split())
        adapter["author"] = (adapter.get("author") or "").strip()
        adapter["source_tag"] = (
            (adapter.get("source_tag") or "").strip().lower()
        )

        tags = adapter.get("tags") or []
        adapter["tags"] = [t.strip().lower() for t in tags if t and t.strip()]

        born_date = (adapter.get("author_born_date") or "").strip()
        try:
            dt = datetime.strptime(born_date, "%B %d, %Y")
            adapter["author_born_date"] = dt.date().isoformat()
        except Exception:
            spider.crawler.stats.inc_value("dropped/invalid_date")
            raise DropItem(f"Invalid author_born_date: {born_date!r}")

        place = (adapter.get("author_born_place") or "").strip()
        adapter["author_born_place"] = re.sub(
            r"^in\s+", "", place, flags=re.IGNORECASE
        )

        bio = adapter.get("author_bio") or ""
        adapter["author_bio"] = " ".join(bio.split())
        adapter["author_url"] = (adapter.get("author_url") or "").strip()

        adapter["business_key"] = (
            f"{adapter['author'].lower()}|"
            f"{adapter['quote'].lower()}|"
            f"{adapter['source_tag']}"
        )


# Дедупликация
class DuplicateFilterPipeline:
    """Дедупликация по бизнес-ключу (UPC для книг, business_key для цитат)."""

    def __init__(self):
        self.seen_books = set()
        self.seen_quotes = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("source") == "books":
            key = adapter.get("upc")
            if key in self.seen_books:
                spider.crawler.stats.inc_value("dropped/duplicates_books")
                raise DropItem(f"Duplicate book: {key}")
            self.seen_books.add(key)
        else:
            key = adapter.get("business_key")
            if key in self.seen_quotes:
                spider.crawler.stats.inc_value("dropped/duplicates_quotes")
                raise DropItem(f"Duplicate quote: {key}")
            self.seen_quotes.add(key)
        return item


# Запись в SQLite
class SQLitePipeline:
    """Пакетная запись в две таблицы: books и quotes."""

    def __init__(self, db_path="data/crawl.db", batch_size=50):
        self.db_path = db_path
        self.batch_size = batch_size
        self.conn = None
        self.batch_books = []
        self.batch_quotes = []

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            db_path=crawler.settings.get("SQLITE_DB_PATH", "data/crawl.db"),
            batch_size=crawler.settings.getint("SQLITE_BATCH_SIZE", 50),
        )

    def open_spider(self, spider):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                upc TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                price_excl_tax REAL,
                availability INTEGER,
                reviews INTEGER,
                category TEXT,
                description TEXT,
                rating INTEGER,
                product_url TEXT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS quotes (
                business_key TEXT PRIMARY KEY,
                quote TEXT NOT NULL,
                author TEXT NOT NULL,
                tags TEXT,
                source_tag TEXT NOT NULL,
                author_born_date TEXT,
                author_born_place TEXT,
                author_bio TEXT,
                author_url TEXT
            )
            """
        )
        self.conn.commit()

    def close_spider(self, spider):
        self._flush(spider)
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if adapter.get("source") == "books":
            self.batch_books.append((
                adapter.get("upc"),
                adapter.get("title"),
                adapter.get("price_excl_tax"),
                adapter.get("availability"),
                adapter.get("reviews"),
                adapter.get("category"),
                adapter.get("description"),
                adapter.get("rating"),
                adapter.get("product_url"),
            ))
            if len(self.batch_books) >= self.batch_size:
                self._flush_books(spider)
        else:
            self.batch_quotes.append((
                adapter.get("business_key"),
                adapter.get("quote"),
                adapter.get("author"),
                ",".join(adapter.get("tags", []) or []),
                adapter.get("source_tag"),
                adapter.get("author_born_date"),
                adapter.get("author_born_place"),
                adapter.get("author_bio"),
                adapter.get("author_url"),
            ))
            if len(self.batch_quotes) >= self.batch_size:
                self._flush_quotes(spider)
        return item

    def _flush_books(self, spider):
        if not self.batch_books:
            return
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO books
            (upc, title, price_excl_tax, availability, reviews,
             category, description, rating, product_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self.batch_books,
        )
        self.conn.commit()
        spider.crawler.stats.inc_value(
            "pipeline/sqlite_written_books", len(self.batch_books)
        )
        self.batch_books.clear()

    def _flush_quotes(self, spider):
        if not self.batch_quotes:
            return
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO quotes
            (business_key, quote, author, tags, source_tag,
             author_born_date, author_born_place, author_bio, author_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self.batch_quotes,
        )
        self.conn.commit()
        spider.crawler.stats.inc_value(
            "pipeline/sqlite_written_quotes", len(self.batch_quotes)
        )
        self.batch_quotes.clear()

    def _flush(self, spider):
        self._flush_books(spider)
        self._flush_quotes(spider)