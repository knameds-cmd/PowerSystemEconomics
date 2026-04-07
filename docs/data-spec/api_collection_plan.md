# API Collection Plan

The project is still in the data-acquisition stage, so the immediate goal is not final modeling code yet. The immediate goal is to collect stable raw inputs in a reproducible way.

## Collection order

1. `smp_forecast_demand`
2. `regional_renewables`
3. `power_market_gen_info`
4. `fuel_cost`
5. `smp_decision_by_fuel`
6. `kpx_member_status`

## Why this order

- `smp_forecast_demand` unlocks representative-day selection and baseline validation fastest.
- `regional_renewables` is required before the renewable-bidding scenario can be framed.
- `power_market_gen_info` and `fuel_cost` are needed for clustering and cost calibration.
- `smp_decision_by_fuel` is validation support rather than the first blocking dependency.
- `kpx_member_status` supports narrative context and can be captured manually.

## Raw staging convention

- Save original API responses first.
- Normalize into CSV only after verifying field names and date conventions.
- Keep one folder per source under `data/raw/`.
- If an API is paginated, keep a simple download log alongside the raw response files.

## Minimum fields to preserve

### SMP / demand

- date
- hour
- mainland SMP
- mainland forecast demand

### Renewable generation

- date
- hour
- region
- solar generation
- wind generation

### Generator info

- area
- company
- central-dispatch flag
- generator name
- generation source
- generation form
- fuel
- capacity

### Fuel cost

- year-month
- fuel type
- unit-price type
- unit
- value

### SMP decision count by fuel

- date
- region
- per-fuel decision counts

## Security rule

- Never store the real API key in markdown, TOML, CSV, or script source committed to Git.
- Use `.env` locally and read from environment variables later.
