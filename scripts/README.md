# Download Scripts

`download_raw_data.ps1` downloads raw API responses into `data/raw/`.
`fetch_data_go_to_csv.py` tries the `data.go.kr` KPX endpoints with Python and writes CSV files when rows are returned.
`fetch_and_standardize_sources.py` fetches approved sources and writes standardized CSV files for analysis and ED preparation.

## Quick start

1. Copy `.env.example` to `.env`
2. Put your decoded service key into `.env`
3. Run one of the examples below

## Examples

Download a minimal current snapshot for every configured source:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_raw_data.ps1
```

Download SMP and fuel-decision data for a specific date range:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_raw_data.ps1 `
  -Source smp_forecast_demand,smp_decision_by_fuel `
  -DateFrom 20250101 `
  -DateTo 20250107
```

Download monthly fuel costs for a month range:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_raw_data.ps1 `
  -Source fuel_cost `
  -MonthFrom 202401 `
  -MonthTo 202412
```

Preview what the script would do without calling any APIs:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download_raw_data.ps1 -DryRun
```

Try the `data.go.kr` APIs with Python and save trial CSV outputs:

```powershell
$env:DATA_GO_KR_SERVICE_KEY='your_key'
& 'C:\Users\kname\AppData\Local\Programs\Python\Launcher\py.exe' .\scripts\fetch_data_go_to_csv.py
```

Fetch approved sources and build standardized CSV files:

```powershell
$env:DATA_GO_KR_SERVICE_KEY='your_key'
& 'C:\Users\kname\AppData\Local\Programs\Python\Launcher\py.exe' .\scripts\fetch_and_standardize_sources.py
```
