"""Метрики качества (≥ 6) + пороги оповещения."""
import json
from pathlib import Path

import pandas as pd

INVERTED = {"duplicate_rate"}


def compute_quality_metrics(df_countries: pd.DataFrame,
                            df_currencies: pd.DataFrame,
                            df_languages: pd.DataFrame,
                            thresholds: dict) -> dict:
    total = max(len(df_countries), 1)
    m = {}

    m["name_completeness"] = {
        "value": round(df_countries["name"].notna().sum() / total, 4),
        "threshold": thresholds.get("name_completeness", 0.98),
        "blocking": True,
    }
    m["capital_completeness"] = {
        "value": round(df_countries["capital"].notna().sum() / total, 4),
        "threshold": thresholds.get("capital_completeness", 0.80),
        "blocking": False,
    }
    m["population_valid"] = {
        "value": round((df_countries["population"].notna() &
                        (df_countries["population"] >= 0)).sum() / total, 4),
        "threshold": thresholds.get("population_valid", 0.95),
        "blocking": True,
    }
    m["area_valid"] = {
        "value": round((df_countries["area_km2"].notna() &
                        (df_countries["area_km2"] >= 0)).sum() / total, 4),
        "threshold": thresholds.get("area_valid", 0.95),
        "blocking": True,
    }
    dup = df_countries.duplicated(subset=["name"]).sum() / total
    m["duplicate_rate"] = {
        "value": round(dup, 4),
        "threshold": thresholds.get("duplicate_rate", 0.05),
        "blocking": True,
    }
    m["api_enrichment_rate"] = {
        "value": round(df_countries["api_match"].sum() / total, 4),
        "threshold": thresholds.get("api_enrichment_rate", 0.90),
        "blocking": False,
    }

    # Метрики для связанных сущностей: сколько стран имеют хотя бы одну валюту/язык
    countries_with_currency = df_currencies["country_name"].nunique() if len(df_currencies) else 0
    m["currency_completeness"] = {
        "value": round(countries_with_currency / total, 4),
        "threshold": thresholds.get("currency_completeness", 0.90),
        "blocking": False,
    }
    countries_with_language = df_languages["country_name"].nunique() if len(df_languages) else 0
    m["language_completeness"] = {
        "value": round(countries_with_language / total, 4),
        "threshold": thresholds.get("language_completeness", 0.90),
        "blocking": False,
    }

    for name, metric in m.items():
        if name in INVERTED:
            metric["status"] = "green" if metric["value"] <= metric["threshold"] else "red"
        else:
            metric["status"] = "green" if metric["value"] >= metric["threshold"] else "red"

    return m


def check_alerts(logger, df_countries, metrics, prev_report_path: str = None) -> list[str]:
    alerts = []

    err = logger.stats["errors"] / max(logger.stats["total"], 1)
    if err > 0.05:
        alerts.append(f"доля ошибок HTTP {err:.1%} > 5%")

    lats = sorted(logger.stats["latencies"])
    med = lats[len(lats) // 2] if lats else 0
    if med > 2.0:
        alerts.append(f"медианная латентность {med:.2f}с > 2с")

    if prev_report_path and Path(prev_report_path).exists():
        prev = json.loads(Path(prev_report_path).read_text(encoding="utf-8"))
        prev_total = prev.get("records_collected", 0)
        if prev_total:
            drop = (prev_total - len(df_countries)) / prev_total
            if drop > 0.3:
                alerts.append(f"объём упал на {drop:.1%} vs предыдущий прогон")

    if any(m["blocking"] and m["status"] == "red" for m in metrics.values()):
        alerts.append("блокирующие метрики не пройдены")

    if metrics["api_enrichment_rate"]["status"] == "red":
        alerts.append(
            f"api_enrichment_rate {metrics['api_enrichment_rate']['value']} < "
            f"{metrics['api_enrichment_rate']['threshold']}"
        )

    return alerts