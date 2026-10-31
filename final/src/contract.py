"""Контракт данных (Pydantic v2): страна, валюта, язык."""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CountryCleanModel(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    capital: Optional[str] = None
    population: Optional[int] = Field(default=None, ge=0)
    area_km2: Optional[float] = Field(default=None, ge=0)
    iso2: Optional[str] = Field(default=None, min_length=2, max_length=2)
    iso3: Optional[str] = Field(default=None, min_length=3, max_length=3)
    region: Optional[str] = None
    currencies: Optional[str] = None
    languages: Optional[str] = None
    api_match: Optional[bool] = None
    source: str = "scrapethissite.com"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Название страны пустое")
        return v.strip()

    @field_validator("population")
    @classmethod
    def population_not_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError(f"Население отрицательное: {v}")
        return v


class CurrencyCleanModel(BaseModel):
    country_name: str = Field(min_length=1, max_length=200)
    iso3: Optional[str] = Field(default=None, min_length=3, max_length=3)
    currency_code: str = Field(min_length=1, max_length=10)
    currency_name: Optional[str] = None
    currency_symbol: Optional[str] = None
    source: str = "restcountries.com"

    @field_validator("currency_code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Код валюты пустой")
        return v.strip().upper()


class LanguageCleanModel(BaseModel):
    country_name: str = Field(min_length=1, max_length=200)
    iso3: Optional[str] = Field(default=None, min_length=3, max_length=3)
    language_name: str = Field(min_length=1, max_length=100)
    language_native: Optional[str] = None
    source: str = "restcountries.com"

    @field_validator("language_name")
    @classmethod
    def lang_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Название языка пустое")
        return v.strip()