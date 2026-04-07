# Data Layout

- `raw/`: original downloaded files from KPX, data.go.kr, or other primary sources
- `processed/`: cleaned and joined datasets ready for representative-day selection and ED inputs

Keep file naming stable so the planned Julia loader can discover inputs predictably.

Recommended raw subfolders:

- `raw/smp_forecast_demand/`
- `raw/renewables/`
- `raw/power_market_gen_info/`
- `raw/fuel_cost/`
- `raw/smp_decision_by_fuel/`
- `raw/reference/`

Do not commit live API keys into this directory or into raw request logs.
