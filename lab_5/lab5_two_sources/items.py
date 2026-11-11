import scrapy


class BookItem(scrapy.Item):
    """Запись с books.toscrape.com."""
    upc = scrapy.Field() # бизнес-ключ
    title = scrapy.Field()
    price_excl_tax = scrapy.Field()
    availability = scrapy.Field()
    reviews = scrapy.Field()
    category = scrapy.Field()
    description = scrapy.Field()
    rating = scrapy.Field()
    product_url = scrapy.Field()
    source = scrapy.Field()


class QuoteItem(scrapy.Item):
    """Запись с quotes.toscrape.com."""
    quote = scrapy.Field()
    author = scrapy.Field()
    tags = scrapy.Field()
    source_tag = scrapy.Field()
    author_born_date = scrapy.Field()
    author_born_place = scrapy.Field()
    author_bio = scrapy.Field()
    author_url = scrapy.Field()
    business_key = scrapy.Field()
    source = scrapy.Field()