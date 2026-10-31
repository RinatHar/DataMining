"""Сбор стран с scrapethissite.com + устойчивость + watermark + ETag."""
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .observability import RunLogger


class CircuitBreaker:
    def __init__(self, threshold: int = 5):
        self.fails = 0
        self.threshold = threshold
        self.open = False

    def record(self, ok: bool):
        if ok:
            self.fails = 0
        else:
            self.fails += 1
            if self.fails >= self.threshold:
                self.open = True


def classify_error(status: int) -> str:
    if status == 0:
        return "network"
    if status in (408, 425, 429, 500, 502, 503, 504):
        return "transient"
    if 400 <= status < 500:
        return "permanent"
    return "ok"


def polite_get(url, session, delay, logger, extra_headers=None,
               max_retries=3, breaker: CircuitBreaker = None):
    """GET с джиттером, классификацией, повторами и предохранителем."""
    if breaker and breaker.open:
        logger.log("circuit_open", url=url)
        return None

    backoff = 1.0
    for attempt in range(max_retries + 1):
        time.sleep(delay + random.uniform(0, 0.15))
        t0 = time.time()
        try:
            resp = session.get(url, headers=extra_headers or {}, timeout=30)
            logger.record_request(resp.status_code, time.time() - t0, url, len(resp.content))
        except requests.RequestException as e:
            logger.record_request(0, time.time() - t0, url)
            if breaker:
                breaker.record(False)
            if attempt == max_retries:
                logger.log("request_failed_final", url=url, error=str(e))
                return None
            logger.stats["retries"] += 1
            time.sleep(backoff)
            backoff *= 2
            continue

        kind = classify_error(resp.status_code)
        if kind == "ok":
            if breaker:
                breaker.record(True)
            return resp
        if kind == "permanent":
            if breaker:
                breaker.record(True)
            return resp

        if breaker:
            breaker.record(False)
        if attempt == max_retries:
            logger.log("request_failed_final", url=url, status=resp.status_code)
            return resp
        wait = float(resp.headers.get("Retry-After", backoff))
        logger.stats["retries"] += 1
        logger.log("retry", url=url, status=resp.status_code, wait=wait)
        time.sleep(wait)
        backoff *= 2
    return None


def collect_countries(config: dict, logger: RunLogger,
                      watermark_path: str, etags_path: str) -> list[dict]:
    """Собирает страны, поддерживая ETag и watermark."""
    url = config["html"]["countries_url"]
    session = requests.Session()
    session.headers.update({"User-Agent": config["html"]["user_agent"]})
    breaker = CircuitBreaker(threshold=5)

    # Watermark
    watermark = {"last_run_date": None}
    wm_file = Path(watermark_path)
    wm_file.parent.mkdir(parents=True, exist_ok=True)
    if wm_file.exists():
        watermark = json.loads(wm_file.read_text(encoding="utf-8"))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if watermark.get("last_run_date") == today:
        print(f"Watermark: уже собрано сегодня ({today}), пропускаем")
        logger.log("watermark_skip", date=today)
        return []

    # ETag
    etags = {}
    etag_file = Path(etags_path)
    etag_file.parent.mkdir(parents=True, exist_ok=True)
    if etag_file.exists():
        etags = json.loads(etag_file.read_text(encoding="utf-8"))

    extra = {}
    if url in etags:
        extra["If-None-Match"] = etags[url]

    resp = polite_get(url, session, config["html"]["delay_seconds"],
                      logger, extra_headers=extra, breaker=breaker)

    if resp is None:
        logger.log("html_failed", url=url)
        return []
    if resp.status_code == 304:
        logger.log("html_not_modified", url=url)
        return []
    if resp.status_code != 200:
        logger.log("html_non_200", status=resp.status_code)
        return []

    if "ETag" in resp.headers:
        etags[url] = resp.headers["ETag"]
        etag_file.write_text(json.dumps(etags, ensure_ascii=False), encoding="utf-8")

    soup = BeautifulSoup(resp.text, "html.parser")
    countries = []

    for div in soup.select("div.country"):
        name_el = div.select_one("h3.country-name")
        if not name_el:
            continue
        name = name_el.text.strip()

        capital_el = div.select_one("span.country-capital")
        pop_el = div.select_one("span.country-population")
        area_el = div.select_one("span.country-area")

        capital = capital_el.text.strip() if capital_el else None
        population = int(pop_el.text.strip()) if pop_el and pop_el.text.strip().isdigit() else None

        area = None
        if area_el:
            try:
                area = float(area_el.text.strip())
            except ValueError:
                pass

        countries.append({
            "name": name,
            "capital": capital,
            "population": population,
            "area_km2": area,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source": "scrapethissite.com",
        })

    watermark["last_run_date"] = today
    watermark["last_run_at"] = datetime.now(timezone.utc).isoformat()
    watermark["total_countries"] = len(countries)
    wm_file.write_text(json.dumps(watermark, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.log("html_collection_finished", total=len(countries))
    return countries