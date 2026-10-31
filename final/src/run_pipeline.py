"""Единая точка входа."""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from .observability import RunLogger
from .collect_html import collect_countries, CircuitBreaker, polite_get
from .collect_api import fetch_rest_countries
from .clean import build_clean
from .storage import init_db, upsert_countries, upsert_currencies, upsert_languages
from .quality import compute_quality_metrics, check_alerts
from .analysis import run_analysis


def demo_resilience(logger):
    import requests

    print("\n=== Демо 503 ===")
    breaker = CircuitBreaker(threshold=2)
    resp = polite_get("https://httpbin.org/status/503",
                     requests.Session(), 0.1, logger,
                     max_retries=1, breaker=breaker)
    status = getattr(resp, 'status_code', None)
    print(f"Статус: {status}; предохранитель открыт: {breaker.open}")

    if breaker.open:
        print("exit code 1")
        import sys
        sys.exit(1)

    print("\n=== Демо 304 ===")
    r1 = requests.get("https://httpbin.org/etag/test-tag")
    r2 = requests.get("https://httpbin.org/etag/test-tag",
                      headers={"If-None-Match": "test-tag"})
    print(f"Первый: {r1.status_code}, повтор: {r2.status_code}")


def main():
    base = Path(__file__).resolve().parent.parent
    cfg = yaml.safe_load((base / "config.yaml").read_text(encoding="utf-8"))

    for d in ["raw", "clean", "mart", "db", "logs", "reports", "state"]:
        (base / d).mkdir(parents=True, exist_ok=True)

    cfg["clean_dir"] = str(base / "clean")

    logger = RunLogger(str(base / "logs" / f"run_{pd.Timestamp.now():%Y%m%d_%H%M%S}.jsonl"))
    logger.log("pipeline_started")

    # HTML
    print("=== Сбор HTML (scrapethissite.com) ===")
    html_countries = collect_countries(
        cfg, logger,
        watermark_path=str(base / "state" / "watermark.json"),
        etags_path=str(base / "state" / "etags.json"),
    )
    print(f"Собрано стран: {len(html_countries)}")
    if not html_countries:
        print("Watermark/304: данные не изменились, выходим")
        sys.exit(0)

    (base / "raw" / "countries.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in html_countries),
        encoding="utf-8",
    )

    # API
    print("\n=== Загрузка REST Countries ===")
    api_result = fetch_rest_countries(cfg, logger)
    print(f"Загружено записей из API: {len(api_result['by_name'])} (индекс), "
          f"{len(api_result['raw'])} (сырых)")

    # Clean
    print("\n=== Очистка ===")
    clean_countries, clean_currencies, clean_languages, rejects = build_clean(
        html_countries, api_result, cfg, logger
    )
    df_countries = pd.DataFrame(clean_countries)
    df_currencies = pd.DataFrame(clean_currencies)
    df_languages = pd.DataFrame(clean_languages)

    df_countries.to_parquet(base / "clean" / "countries_clean.parquet", index=False)
    df_currencies.to_parquet(base / "clean" / "currencies_clean.parquet", index=False)
    df_languages.to_parquet(base / "clean" / "languages_clean.parquet", index=False)

    total_records = len(df_countries) + len(df_currencies) + len(df_languages)
    print(f"Чистый слой: {total_records} записей "
          f"(страны={len(df_countries)}, валюты={len(df_currencies)}, языки={len(df_languages)})")

    # Storage
    print("\n=== Загрузка в БД (3 прогона) ===")
    conn = init_db(str(base / cfg["db"]["path"]))
    for n in range(1, 4):
        ins_c, upd_c = upsert_countries(conn, clean_countries)
        ins_cur, upd_cur = upsert_currencies(conn, clean_currencies)
        ins_l, upd_l = upsert_languages(conn, clean_languages)
        total_c = conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
        total_cur = conn.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
        total_l = conn.execute("SELECT COUNT(*) FROM languages").fetchone()[0]
        print(f"Прогон {n}: countries={total_c}, currencies={total_cur}, languages={total_l}")

    # Quality
    print("\n=== Метрики качества ===")
    metrics = compute_quality_metrics(df_countries, df_currencies, df_languages,
                                     cfg["quality"]["thresholds"])
    blocking_fail = False
    for name, m in metrics.items():
        icon = "green" if m["status"] == "green" else "red"
        kind = "блок." if m["blocking"] else "инфо"
        print(f"{icon} [{kind:5}] {name}: {m['value']} (порог {m['threshold']})")
        if m["blocking"] and m["status"] != "green":
            blocking_fail = True

    verdict = "FAIL — mart заблокирован" if blocking_fail else "PASS"
    print(f"\nВердикт: {verdict}")

    # Alerts
    print("\n=== Пороги оповещения ===")
    prev_reports = sorted((base / "reports").glob("run_report_*.json"))
    prev_path = str(prev_reports[-1]) if prev_reports else None
    alerts = check_alerts(logger, df_countries, metrics, prev_path)
    if alerts:
        for a in alerts:
            print(f"Внимание {a}")
    else:
        print("Все пороги в норме")

    # Отчёт
    report = logger.build_report(collected=total_records, rejected=len(rejects))
    report_path = base / "reports" / f"run_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nОтчёт: {report_path}")

    # Аналитика
    if not blocking_fail:
        run_analysis(cfg["clean_dir"], str(base / "mart"))

    # Демонстрация
    demo_resilience(logger)

    if blocking_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()