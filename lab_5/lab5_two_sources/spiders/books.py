import json
import os
from datetime import datetime

import scrapy

from lab5_two_sources.items import BookItem


class BooksSpider(scrapy.Spider):
    """Паук для books.toscrape.com — двухуровневый обход каталога."""

    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]

    def parse(self, response):
        """Уровень 1: страница каталога (пагинация)."""
        # ссылки на карточки книг
        for link in response.css("article.product_pod h3 a::attr(href)").getall():
            yield response.follow(
                link,
                callback=self.parse_item,
                errback=self.errback,
            )

        # пагинация
        next_href = response.css("li.next a::attr(href)").get()
        if next_href:
            yield response.follow(
                next_href,
                callback=self.parse,
                errback=self.errback,
            )

    def parse_item(self, response, **_kw):
        """Уровень 2: карточка книги."""
        item = BookItem()
        item["source"] = "books"
        item["product_url"] = response.url

        # название
        title = response.css("h1::text").get()
        item["title"] = title.strip() if title else None

        # UPC, наличие, отзывы, цена — из таблицы product information
        upc = response.css(
            'table.table-striped tr td::text'
        ).getall()
        # более надёжно: брать td, соответствующие th
        ths = response.css("table.table-striped th::text").getall()
        tds = response.css("table.table-striped td::text").getall()
        info = {k.strip(): v.strip() for k, v in zip(ths, tds)}

        item["upc"] = info.get("UPC")
        item["price_excl_tax"] = info.get("Price (excl. tax)")
        item["availability"] = info.get("Availability")
        item["reviews"] = info.get("Number of reviews")

        # категория — из breadcrumb
        crumbs = response.css("ul.breadcrumb li a::text").getall()
        item["category"] = crumbs[-1].strip() if crumbs else None

        # рейтинг
        rating_classes = response.css(
            "div.product_main p.star-rating::attr(class)"
        ).get()
        if rating_classes:
            parts = rating_classes.split()
            item["rating"] = next(
                (p for p in parts if p != "star-rating"), ""
            )
        else:
            item["rating"] = ""

        # описание (может отсутствовать)
        desc = response.css(
            "#product_description ~ p::text"
        ).get()
        item["description"] = desc.strip() if desc else ""

        yield item

    def errback(self, failure):
        self.logger.error("Request failed: %s", failure.request.url)
        self.crawler.stats.inc_value("errback/errors")

    def closed(self, reason):
        stats = self.crawler.stats.get_stats()
        stats["close_reason"] = reason
        os.makedirs("data", exist_ok=True)
        fname = (
            f"data/stats_books_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
        self.logger.info("Stats saved to %s", fname)