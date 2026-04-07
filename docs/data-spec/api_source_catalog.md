# API Source Catalog

This document turns the approval screenshots, provider guide documents, and the workbook in `data_information.xlsx` into a single working reference for the project.

## Secret handling

- The real service key was visible in the screenshots but is intentionally not stored in this repository.
- Put the decoded key in a local `.env` file based on `.env.example`.
- Use the same environment-variable names from `config/data_sources.template.toml` when download scripts are added later.

## Approved core sources

| Key | Required | Source | Endpoint / Reference | Project role | Approval status from screenshots |
| --- | --- | --- | --- | --- | --- |
| `smp_forecast_demand` | Yes | data.go.kr / KPX | `https://apis.data.go.kr/B552115/SmpWithForecastDemand/getSmpWithForecastDemand` | Mainland SMP and forecast-demand baseline | Approved |
| `regional_renewables` | Yes | odcloud / KPX | Swagger: `https://infuser.odcloud.kr/oas/docs?namespace=15065269/v1` | Hourly solar and wind availability inputs | Approved |
| `power_market_gen_info` | Yes | data.go.kr / KPX | `https://apis.data.go.kr/B552115/PowerMarketGenInfo/getPowerMarketGenInfo` | Generator metadata for clustering | Approved |
| `fuel_cost` | Yes | data.go.kr / KPX | `https://apis.data.go.kr/B552115/FuelCost1/getFuelCost1` | Monthly fuel-cost anchor | Approved |
| `smp_decision_by_fuel` | Yes | data.go.kr / KPX | `https://apis.data.go.kr/B552115/SmpDecByFuel2/getSmpDecByFuel2` | Daily marginal-fuel validation support | Approved |
| `kpx_member_status` | No | KPX website | Manual web page reference | Market-structure narrative context | Captured as reference |

## Request details by source

### 1. SMP and Forecast Demand

- Dataset: `한국전력거래소_계통한계가격 및 수요예측(하루전 발전계획용)`
- Service type: REST
- Format: JSON + XML
- Base endpoint: `https://apis.data.go.kr/B552115/SmpWithForecastDemand`
- Operation: `getSmpWithForecastDemand`
- Daily traffic shown in screenshot: `100`
- Expected use in this project:
  - actual mainland SMP validation target for `Pre-revision ED`
  - load time series for representative-day selection
  - later comparison plots and duration curves

### 2. Regional Solar and Wind Generation

- Dataset: `한국전력거래소_지역별 시간별 태양광 및 풍력 발전량`
- Service type: REST
- Format: JSON + XML
- Base API: `https://api.odcloud.kr/api`
- Swagger reference: `https://infuser.odcloud.kr/oas/docs?namespace=15065269/v1`
- Screenshot note: approval active from `2026-04-07`
- Expected use in this project:
  - solar and wind hourly availability
  - national aggregation for the single-node mainland model
  - renewable-bid block capacity inputs in `Post-revision ED`

### 3. Power Market Generator Info

- Dataset: `한국전력거래소_전력시장 발전설비 정보`
- Service type: REST
- Format: JSON + XML
- Base endpoint: `https://apis.data.go.kr/B552115/PowerMarketGenInfo`
- Operation: `getPowerMarketGenInfo`
- Daily traffic shown in screenshot: `100`
- Original guide copied into repo: `docs/data-spec/api-guides/오픈API활용가이드_전력시장발전설비정보.docx`
- Key request parameters from the provider guide:
  - `serviceKey` required
  - `pageNo` required
  - `numOfRows` required
  - `dataType` required
  - `genNm` optional
- Key response fields from the provider guide:
  - `area`
  - `company`
  - `cent`
  - `genNm`
  - `genSrc`
  - `genFom`
  - `fuel`
  - `pcap`
- Expected use in this project:
  - clustering into nuclear, coal, LNG, oil, CHP, hydro, and related groups
  - capacity aggregation for ED bounds

### 4. Monthly Fuel Cost

- Dataset: `한국전력거래소_월간 연료비용 정보`
- Service type: REST
- Format: JSON + XML
- Base endpoint: `https://apis.data.go.kr/B552115/FuelCost1`
- Operation: `getFuelCost1`
- Original guide copied into repo: `docs/data-spec/api-guides/오픈API활용가이드_월간연료비용정보.docx`
- Key request parameters from the provider guide:
  - `serviceKey` required
  - `pageNo` required
  - `numOfRows` required
  - `dataType` required
  - `day` optional, `YYYYMM`
  - `fuelType` optional
- Key response fields from the provider guide:
  - `untpcType`
  - `fuelType`
  - `unit`
  - `day`
  - `untpc`
- Expected use in this project:
  - monthly fuel-cost anchor
  - effective marginal-cost construction for `Pre-revision ED`

### 5. Daily SMP Decision Count by Fuel

- Dataset: `한국전력거래소_연료원별 SMP 결정 횟수(일별)`
- Service type: REST
- Format: JSON + XML
- Base endpoint: `https://apis.data.go.kr/B552115/SmpDecByFuel2`
- Operation: `getSmpDecByFuel2`
- Expected use in this project:
  - direction check for marginal fuel mix
  - model validation against actual price-setting tendencies

### 6. KPX Member Status

- Reference page: `회원사 현황 (2024년 12월 말 기준)`
- Transcribed repo file: `data/raw/reference/kpx_member_status_2024-12.md`
- Use case:
  - report section on market structure and participant composition
  - descriptive context only, not a primary optimization input

## Mapping to workbook sheets

| Workbook sheet | Source key |
| --- | --- |
| `①SMP_수요` | `smp_forecast_demand` |
| `②재생에너지` | `regional_renewables` |
| `③발전설비` | `power_market_gen_info` |
| `④연료비용` | `fuel_cost` |
| `⑤SMP결정횟수` | `smp_decision_by_fuel` |
| narrative market structure | `kpx_member_status` |

## Recommended raw file naming

Use file names that can be recognized later by `load_data.jl`.

- `data/raw/smp_forecast_demand/smp_forecast_demand_YYYYMM_YYYYMM.csv`
- `data/raw/renewables/renewables_hourly_YYYYMM_YYYYMM.csv`
- `data/raw/power_market_gen_info/power_market_gen_info_YYYYMMDD.csv`
- `data/raw/fuel_cost/fuel_cost_YYYYMM.csv`
- `data/raw/smp_decision_by_fuel/smp_decision_by_fuel_YYYYMM_YYYYMM.csv`
- `data/raw/reference/kpx_member_status_2024-12.md`

## Notes for the next implementation step

- The odcloud renewable source should be checked in Swagger before writing a downloader because the generated path and pagination can differ from the classic data.go.kr pattern.
- For the KPX data.go.kr endpoints, the first implementation should request JSON, save the raw response, and then normalize to CSV in a separate step.
- If you later automate collection, keep API keys out of PowerShell history and commit history.
