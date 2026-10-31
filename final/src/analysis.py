"""Аналитика: 4 графика + выводы + ограничения."""
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def run_analysis(clean_dir: str, out_dir: str):
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    df_countries = pd.read_parquet(f"{clean_dir}/countries_clean.parquet")
    df_currencies = pd.read_parquet(f"{clean_dir}/currencies_clean.parquet")
    df_languages = pd.read_parquet(f"{clean_dir}/languages_clean.parquet")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Топ-10 по населению
    top_pop = df_countries.dropna(subset=["population"]).nlargest(10, "population")
    axes[0, 0].barh(top_pop["name"], top_pop["population"], color="steelblue")
    axes[0, 0].set_title("Топ-10 стран по населению")
    axes[0, 0].invert_yaxis()

    # Регионы
    region_counts = df_countries["region"].value_counts()
    axes[0, 1].bar(region_counts.index, region_counts.values, color="coral")
    axes[0, 1].set_title("Количество стран по регионам")
    axes[0, 1].tick_params(axis="x", rotation=45)

    # Топ-10 языков по числу стран
    lang_counts = df_languages["language_name"].value_counts().head(10)
    axes[1, 0].barh(lang_counts.index, lang_counts.values, color="seagreen")
    axes[1, 0].set_title("Топ-10 языков по числу стран")
    axes[1, 0].invert_yaxis()

    # Scatter: население ↔ площадь
    df_scatter = df_countries.dropna(subset=["population", "area_km2"]).copy()
    df_scatter = df_scatter[(df_scatter["population"] > 0) & (df_scatter["area_km2"] > 0)]

    x = df_scatter["area_km2"]
    y = df_scatter["population"]
    axes[1, 1].scatter(x, y, alpha=0.5, color="purple", s=20)
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_xlabel("Площадь, км² (log)")
    axes[1, 1].set_ylabel("Население (log)")
    corr = x.corr(y)
    axes[1, 1].set_title(f"Население ↔ площадь (r = {corr:.3f})")

    plt.tight_layout()
    plt.savefig(out / "analysis_plots.png", dpi=150)
    plt.close()

    print(f"\n=== Выводы ===")
    print(f"1. Корреляция население↔площадь: {corr:.3f}")
    print(f"2. Регионов: {df_countries['region'].nunique()}; "
          f"больше всего стран в {region_counts.index[0]} ({region_counts.iloc[0]})")
    print(f"3. Всего валют: {len(df_currencies)}; языков: {len(df_languages)}; "
          f"обогащение API: {df_countries['api_match'].mean():.1%}")
    print("\n=== Ограничения ===")
    print("  - 250 стран из HTML, не весь мир.")
    print("  - ~6% стран не сопоставились по названию.")
    print("  - Данные о населении на HTML-странице устаревшие.")