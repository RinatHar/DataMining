"""Обогащение через REST Countries API v5 (пагинация + Bearer)."""
import random
import time

import requests

from .observability import RunLogger


def _fetch_page(config, session, logger, offset: int = 0) -> list:
    url = config["api"]["all_url"]
    headers = {
        "User-Agent": config["api"]["user_agent"],
        "Authorization": f"Bearer {config['api']['api_key']}",
    }
    params = {"limit": 100, "offset": offset}

    time.sleep(config["api"]["delay_seconds"] + random.uniform(0, 0.1))
    t0 = time.time()
    try:
        resp = session.get(url, headers=headers, params=params, timeout=30)
        logger.record_request(resp.status_code, time.time() - t0, resp.url, len(resp.content))
    except requests.RequestException as e:
        logger.record_request(0, time.time() - t0, url)
        logger.log("api_request_failed", error=str(e))
        return []

    if resp.status_code != 200:
        logger.log("api_non_200", status=resp.status_code, body=resp.text[:200])
        return []

    try:
        data = resp.json()
    except ValueError:
        logger.log("api_json_decode_failed")
        return []

    objects = data.get("data", {}).get("objects", [])
    return objects if isinstance(objects, list) else []


def fetch_rest_countries(config: dict, logger: RunLogger) -> dict:
    """Возвращает:
      {
        "by_name": {name_lower: {...}},
        "raw": [...],   # сырые записи API
      }
    """
    session = requests.Session()
    all_objects = []
    offset = 0
    while True:
        page = _fetch_page(config, session, logger, offset)
        if not page:
            break
        all_objects.extend(page)
        if len(page) < 100:
            break
        offset += 100

    logger.log("api_enrichment_loaded", total_countries=len(all_objects))
    print(f"Загружено стран из v5: {len(all_objects)}")

    by_name = {}
    for c in all_objects:
        names = c.get("names", {}) if isinstance(c.get("names"), dict) else {}
        name_common = names.get("common", "") or ""
        name_official = names.get("official", "") or ""

        codes = c.get("codes", {}) if isinstance(c.get("codes"), dict) else {}
        currencies = c.get("currencies")
        languages = c.get("languages")
        capitals = c.get("capitals")
        area = c.get("area")

        record = {
            "iso2": codes.get("alpha_2"),
            "iso3": codes.get("alpha_3"),
            "region": c.get("region"),
            "currencies": ", ".join(cur.get("code", "") for cur in currencies) if isinstance(currencies, list) else None,
            "languages": ", ".join(lang.get("name", "") for lang in languages) if isinstance(languages, list) else None,
            "capital": capitals[0].get("name") if isinstance(capitals, list) and capitals else None,
            "population": c.get("population"),
            "area": area.get("kilometers") if isinstance(area, dict) else None,
        }

        if name_common:
            by_name[name_common.lower().strip()] = record
        if name_official:
            by_name[name_official.lower().strip()] = record

    logger.log("api_index_built", indexed_names=len(by_name))
    return {"by_name": by_name, "raw": all_objects}