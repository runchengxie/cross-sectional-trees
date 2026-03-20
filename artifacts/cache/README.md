# Data Cache Metadata

This directory contains cached daily OHLCV data from data providers.

## Structure

Each file is named `{symbol}.parquet` and contains daily bars for that symbol.

## Schema

| Field | Type | Description |
|-------|------|-------------|
| ts_code | string | Stock symbol |
| trade_date | date | Trading date |
| open | float | Open price |
| high | float | High price |
| low | float | Low price |
| close | float | Close price |
| volume | float | Volume |
| total_turnover | float | Total turnover in HKD |

## Metadata

| Property | Value |
|----------|-------|
| Cache version | 20260314 |
| Date range | 2015-01-01 to 2026-03-14 |
| Symbols | ~1523 |
| Source | RQData |
| Total records | ~2.8M |

## Notes

- This is a runtime cache, can be deleted and regenerated.
- Files are organized by symbol for efficient loading.
