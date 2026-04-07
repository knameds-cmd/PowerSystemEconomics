# Download Status (2026-04-07)

## Completed

- `regional_renewables`
  - Source: odcloud / KPX
  - Result: downloaded successfully into `data/raw/renewables/`
  - Basis: latest Swagger path for `한국전력거래소_지역별 시간별 태양광 및 풍력 발전량`

## Blocked

- `smp_forecast_demand`
- `power_market_gen_info`
- `fuel_cost`
- `smp_decision_by_fuel`

### Blocker detail

An external download attempt against the approved `data.go.kr` KPX endpoints returned HTTP `401 Unauthorized` for multiple services on `2026-04-07`.

The same result was reproduced with a Python ingestion path that attempted to convert the responses into pandas DataFrames and CSV files under `data/processed/python_trials/`.

### What this likely means

- the currently used key is not the exact working key for these endpoints, or
- the portal is expecting a different key form, or
- the account approval has not propagated to the callable endpoint environment yet

### Next check to unblock

Confirm the exact working `data.go.kr` key format to use locally in `.env`, then rerun:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_raw_data.ps1 -Source smp_forecast_demand
```
