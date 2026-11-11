BOT_NAME = "lab5_two_sources"

SPIDER_MODULES = ["lab5_two_sources.spiders"]
NEWSPIDER_MODULE = "lab5_two_sources.spiders"

# Вежливость
ROBOTSTXT_OBEY = True
USER_AGENT = (
    "EducationalCrawler/1.0 "
    "(+https://example.edu; contact: student@example.edu)"
)

CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 1.0

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

DOWNLOAD_TIMEOUT = 30
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408]

# Предохранители
DEPTH_LIMIT = 8
CLOSESPIDER_ITEMCOUNT = 350 # итоговый прогон
CLOSESPIDER_TIMEOUT = 0
CLOSESPIDER_PAGECOUNT = 0

# HTTP-кэш для отладки
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [500, 502, 503, 504, 408]

LOG_LEVEL = "INFO"

# Пайплайны
ITEM_PIPELINES = {
    "lab5_two_sources.pipelines.ValidatePipeline": 100,
    "lab5_two_sources.pipelines.CleanPipeline": 200,
    "lab5_two_sources.pipelines.DuplicateFilterPipeline": 300,
    "lab5_two_sources.pipelines.SQLitePipeline": 400,
}

#  Feed Export
FEEDS = {
    "data/items.jsonl": {
        "format": "jsonlines",
        "encoding": "utf8",
        "overwrite": True,
    },
}

# БД
SQLITE_DB_PATH = "data/crawl.db"
SQLITE_BATCH_SIZE = 50