"""Очистка: соединение HTML и API, контракт для трёх сущностей, rejects."""
import json
from datetime import datetime, timezone
from pydantic import ValidationError

from .contract import CountryCleanModel, CurrencyCleanModel, LanguageCleanModel
from .observability import RunLogger


def build_clean(html_countries: list[dict], api_result: dict,
                config: dict, logger: RunLogger):
    """
    Возвращает (clean_countries, clean_currencies, clean_languages, rejects).
    """
    by_name = api_result["by_name"]
    raw_api = api_result["raw"]

    clean_countries, clean_currencies, clean_languages, rejects = [], [], [], []
    matched = 0

    # Страны
    for c in html_countries:
        name_key = c["name"].lower().strip()
        api = by_name.get(name_key)
        if api is None:
            api = {}
        else:
            matched += 1

        raw = {
            "name": c["name"],
            "capital": c.get("capital") or api.get("capital"),
            "population": c.get("population") if c.get("population") is not None else api.get("population"),
            "area_km2": c.get("area_km2") if c.get("area_km2") is not None else api.get("area"),
            "iso2": api.get("iso2"),
            "iso3": api.get("iso3"),
            "region": api.get("region"),
            "currencies": api.get("currencies"),
            "languages": api.get("languages"),
            "api_match": bool(api),
            "source": c["source"],
        }
        try:
            clean_countries.append(CountryCleanModel(**raw).model_dump())
        except ValidationError as e:
            rejects.append({"stage": "country", "raw": raw, "errors": e.errors(),
                            "rejected_at": datetime.now(timezone.utc).isoformat()})

    # Валюты (разворачиваем из raw API)
    for c in raw_api:
        names = c.get("names", {}) if isinstance(c.get("names"), dict) else {}
        country_name = names.get("common", "") or ""
        codes = c.get("codes", {}) if isinstance(c.get("codes"), dict) else {}
        iso3 = codes.get("alpha_3")

        currencies = c.get("currencies")
        if not isinstance(currencies, list):
            continue
        for cur in currencies:
            if not isinstance(cur, dict):
                continue
            raw = {
                "country_name": country_name,
                "iso3": iso3,
                "currency_code": cur.get("code", ""),
                "currency_name": cur.get("name"),
                "currency_symbol": cur.get("symbol"),
                "source": "restcountries.com",
            }
            try:
                clean_currencies.append(CurrencyCleanModel(**raw).model_dump())
            except ValidationError as e:
                rejects.append({"stage": "currency", "raw": raw, "errors": e.errors(),
                                "rejected_at": datetime.now(timezone.utc).isoformat()})

    # Языки (разворачиваем из raw API)
    for c in raw_api:
        names = c.get("names", {}) if isinstance(c.get("names"), dict) else {}
        country_name = names.get("common", "") or ""
        codes = c.get("codes", {}) if isinstance(c.get("codes"), dict) else {}
        iso3 = codes.get("alpha_3")

        languages = c.get("languages")
        if not isinstance(languages, list):
            continue
        for lang in languages:
            if not isinstance(lang, dict):
                continue
            raw = {
                "country_name": country_name,
                "iso3": iso3,
                "language_name": lang.get("name", ""),
                "language_native": lang.get("native_name"),
                "source": "restcountries.com",
            }
            try:
                clean_languages.append(LanguageCleanModel(**raw).model_dump())
            except ValidationError as e:
                rejects.append({"stage": "language", "raw": raw, "errors": e.errors(),
                                "rejected_at": datetime.now(timezone.utc).isoformat()})

    # Rejects
    with open(f"{config['clean_dir']}/rejects.jsonl", "a", encoding="utf-8") as f:
        for r in rejects:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    logger.log("cleaning_finished",
               countries=len(clean_countries),
               currencies=len(clean_currencies),
               languages=len(clean_languages),
               rejects=len(rejects),
               api_matched=matched)
    print(f"Соединение HTML↔API: совпало {matched} из {len(html_countries)} "
          f"({matched / max(len(html_countries), 1):.1%})")
    print(f"Чистый слой: страны={len(clean_countries)}, "
          f"валюты={len(clean_currencies)}, языки={len(clean_languages)}")
    return clean_countries, clean_currencies, clean_languages, rejects