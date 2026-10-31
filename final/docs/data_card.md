# Паспорт данных (Data Card)

## Происхождение
- HTML: scrapethissite.com/pages/simple/ — 250 стран.
- API: api.restcountries.com/countries/v5 — 254 страны, валюты, языки.

## Состав полей

### countries (~250 записей)
| Поле | Тип | Источник |
|---|---|---|
| name | str | HTML |
| capital | str? | HTML / API |
| population | int? | HTML / API |
| area_km2 | float? | HTML / API |
| iso2 / iso3 | str? | API |
| region | str? | API |
| currencies | str? | API |
| languages | str? | API |
| api_match | bool | вычисляется |

### currencies (~272 записи)
| Поле | Тип | Источник |
|---|---|---|
| country_name | str | API |
| iso3 | str? | API |
| currency_code | str | API |
| currency_name | str? | API |
| currency_symbol | str? | API |

### languages (~425 записей)
| Поле | Тип | Источник |
|---|---|---|
| country_name | str | API |
| iso3 | str? | API |
| language_name | str | API |
| language_native | str? | API |

## Итого: ~947 связанных записей

## Частота обновления
По требованию (cron 03:00 UTC).

## Возобновляемость
watermark в `state/watermark.json`; ETag в `state/etags.json`.

## Известные ограничения
- 250 стран из HTML — не весь мир.
- ~6% не сопоставились по названию.
- Данные о населении на HTML-странице устаревшие.

## Лицензия
- scrapethissite.com: учебная песочница.
- REST Countries: MPL-2.0.