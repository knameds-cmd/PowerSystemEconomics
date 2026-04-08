# 데이터 파일 현황 보고서

> 작성일: 2026-04-09  
> 대상 기간: 2024-01-01 ~ 2024-12-31 (366일, 윤년)  
> 기준 문서: `DATA_SPECIFICATION.md`  
> 저장 위치: `project/data/raw/`

---

## 1. 전체 현황 요약

| # | 파일명 | 행 수 | 상태 | 데이터 소스 |
|---|--------|-------|------|-----------|
| 1 | `smp_demand.csv` | 8,784 | **실데이터 완료** | EPSIS 시간별SMP + KPX 전력수요량 |
| 2 | `재생에너지_발전량_2024.csv` | 8,784 | **실데이터 완료** | KPX 재생에너지 발전량 |
| 3 | `generators.csv` | 9 | **부분 완료** | EPSIS 발전기세부내역 + 추정값 |
| 4 | `fuel_costs.csv` | 72 | **실데이터 완료** | EPSIS 전력거래 연료비용 (열량단가) |
| 5 | `gencost.csv` | 9 | **실데이터 완료** | KPG193_ver1_5 MATPOWER 데이터 |
| 6 | `genthermal.csv` | 9 | **실데이터 완료** | KPG193_ver1_5 MATPOWER 데이터 |
| 7 | `nuclear_must_off.csv` | 18 | **실데이터 완료** | 한국수력원자력 계획예방정비 현황 |
| 8 | `marginal_fuel_counts.csv` | 366 | **실데이터 완료** (월→일 배분) | EPSIS 연료원별 SMP결정횟수 |

---

## 2. 파일별 상세

### 2.1 `smp_demand.csv` — SMP 실적 및 전력수요

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료** |
| 행 수 | 8,784 (366일 x 24시간) |
| 컬럼 | `날짜`, `거래시간`, `smp_육지`, `수요_육지` |
| 원본 | `HOME_전력거래_계통한계가격_시간별SMP.csv` + `한국전력거래소_시간별 전국 전력수요량_20241231.csv` |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_smp_demand.py` |

**데이터 통계:**

| 지표 | SMP (원/MWh) | 수요 (MW) |
|------|-------------|----------|
| 최솟값 | 0 | 39,258 |
| 최댓값 | 230,820 | 97,115 |
| 평균 | 125,437 | 64,534 |
| 중위수 | 133,115 | - |

**특이사항:**
- SMP 원본은 원/kWh 단위 → x1000 변환하여 원/MWh로 저장
- SMP=0인 시간대가 6건 존재 (2/10, 2/11, 2/12, 11/3, 11/23, 11/24 정오 부근) — 재생에너지 과잉 발전 시 실제 발생하는 현상

---

### 2.2 `재생에너지_발전량_2024.csv` — 태양광/풍력 발전량

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료** |
| 행 수 | 8,784 |
| 컬럼 | `날짜`, `거래시간`, `태양광_합계`, `풍력_육지` |
| 원본 | KPX 재생에너지 발전량 (기존 확보 데이터) |
| 결측치 | 없음 |

**데이터 범위:**

| 지표 | 태양광 (MW) | 풍력_육지 (MW) |
|------|-----------|--------------|
| 최솟값 | 0.0 | 0.02 |
| 최댓값 | 6,255 | 1,266 |
| 평균 | 1,209 | 343 |

---

### 2.3 `generators.csv` — 9개 열발전 클러스터

| 항목 | 내용 |
|------|------|
| 상태 | **부분 완료 (보완 필요)** |
| 행 수 | 9 |
| 컬럼 | `name`, `fuel`, `pmin`, `pmax`, `ramp_up`, `ramp_down`, `heat_rate`, `vom`, `must_run`, `marginal_cost` |
| 원본 | `HOME_발전설비_발전기세부내역.csv` (중앙급전 321기) + 연료비용 기반 산출 |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_generators.py` |

**클러스터 구성:**

| 클러스터 | 연료 | Pmax (MW) | Pmin (MW) | must_run | MC (원/MWh) |
|---------|------|----------|----------|----------|-----------|
| Nuclear_base | nuclear | 23,950 | 17,962 | true | 6,688 |
| Coal_lowcost | coal | 18,954 | 7,582 | false | 73,945 |
| Coal_highcost | coal | 18,955 | 7,582 | false | 81,297 |
| LNG_CC_low | lng | 13,290 | 3,987 | false | 140,526 |
| LNG_CC_mid | lng | 13,290 | 3,987 | false | 149,116 |
| CHP_mustrun | chp | 6,000 | 4,000 | true | 139,526 |
| LNG_GT_peak | lng | 17,720 | 0 | false | 207,244 |
| Oil_peak | oil | 700 | 0 | false | 427,801 |
| Hydro_fixed | hydro | 6,282 | 0 | false | 500 |
| **합계** | | **119,141** | **45,100** | | |

> 2024년 피크수요 97,115 MW 대비 예비율 약 22.7%

#### 실데이터 기반 컬럼 (신뢰도 높음)

| 컬럼 | 산출 방법 |
|------|----------|
| `name`, `fuel` | 9개 클러스터 체계 (DATA_SPEC 정의) |
| `pmax` | EPSIS 발전기세부내역 중앙급전 연료별 설비용량 합산 |
| `marginal_cost` | 2024년 실제 연료단가 x heat_rate + vom |

#### 추정값 사용 컬럼 (보완 필요)

| 컬럼 | 현재 추정 방법 | 보완에 필요한 데이터 |
|------|-------------|-------------------|
| `pmin` | 연료별 경험적 비율 적용 (원전 75%, 석탄 40%, LNG CC 30%) | 발전기별 기술적 최소출력 |
| `ramp_up/down` | Pmax의 일정 비율 (12%, 10%, 30% 등) | 발전기별 실제 램프율 |
| `heat_rate` | DATA_SPEC 참조값 (2.4, 2.1, 2.3, 1.7, 1.8 등) | 클러스터별 가중평균 열소비율 (전력시장운영규칙) |
| `vom` | DATA_SPEC 참조값 (500~8,000 원/MWh) | 전력시장운영규칙 변동운영비 기준 |
| CHP `pmax` | 6,000 MW (DATA_SPEC 추정치) | 발전기세부내역에 CHP 분류 없어 별도 확인 필요 |
| Coal 분할 | 50/50 균등 분할 | 개별 석탄 발전기 비용 순위 정보 |
| LNG CC/GT 비율 | 60%/40% 추정 | 복합(CC)/단순(GT) 가스터빈 구분 정보 |

---

### 2.4 `fuel_costs.csv` — 월별 연료 단가

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료** |
| 행 수 | 72 (12개월 x 6개 연료) |
| 컬럼 | `year_month`, `fuel`, `fuel_cost` |
| 원본 | `HOME_전력거래_연료비용.csv` 열량단가(원/Gcal) 섹션 |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_fuel_costs.py` |

**2024년 연료별 단가 범위 (원/Gcal):**

| 연료 | 최솟값 | 최댓값 | 비고 |
|------|--------|--------|------|
| nuclear | 2,566 | 2,585 | 안정적 |
| coal | 32,041 | 36,135 | 유연탄 기준 |
| lng | 74,578 | 94,373 | 변동성 큼 |
| oil | 125,116 | 147,127 | 유류 |
| chp | 63,392 | 80,217 | LNG 단가 x 0.85 적용 |
| hydro | 0 | 0 | 연료비 없음 |

**특이사항:**
- CHP 연료단가는 LNG 기반 열병합으로 LNG 단가의 85% 수준으로 산출
- hydro는 연료비 0 (기회비용은 VOM에 반영)

---

### 2.5 `gencost.csv` — 2차 비용함수 계수

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료 (KPG193)** |
| 행 수 | 9 |
| 컬럼 | `name`, `a`, `b`, `c` |
| 원본 | KPG193_ver1_5.m → `mpc.gencost` (122개 발전기) |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_gencost_genthermal.py` |

**클러스터링 방법:**
- 122개 발전기를 연료별 + 비용 수준별로 9개 클러스터에 배정
- Coal: MC@50%load 중위수 기준 lowcost/highcost 분할
- LNG: Pmax >= 400MW → CC (비용 기준 low/mid), < 400MW → GT
- 각 계수는 클러스터 내 Pmax 가중평균으로 산출

**비용함수: C(P) = a x P^2 + b x P + c**

| 클러스터 | a | b (원/MWh) | c | MC@50%load |
|---------|---|-----------|---|------------|
| Nuclear_base | 0.002277 | 5,580 | 0 | 5,636 |
| Coal_lowcost | 0.026937 | 24,063 | 1,883 | 24,600 |
| Coal_highcost | 0.029615 | 26,422 | 2,124 | 26,961 |
| LNG_CC_low | 0.004174 | 50,090 | 4,768 | 50,174 |
| LNG_CC_mid | 0.005076 | 59,788 | 5,217 | 59,894 |
| CHP_mustrun | 0.003500 | 80,000 | 40,000 | *(기본값)* |
| LNG_GT_peak | 0.005346 | 36,872 | 638 | 36,873 |
| Oil_peak | 0.008000 | 210,000 | 5,000 | *(기본값)* |
| Hydro_fixed | 0.000000 | 60,000 | 0 | *(기본값)* |

> CHP/Oil/Hydro는 KPG193에 미포함 → DATA_SPECIFICATION 기본값 사용

---

### 2.6 `genthermal.csv` — 기동비 및 최소가동시간

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료 (KPG193)** |
| 행 수 | 9 |
| 컬럼 | `name`, `startup_cost`, `min_up_time`, `pmax_unit` |
| 원본 | KPG193_ver1_5.m → `mpc.genthermal` (122개 발전기) |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_gencost_genthermal.py` |

| 클러스터 | startup_cost (천원) | min_up_time (h) | pmax_unit (MW) |
|---------|-------------------|----------------|---------------|
| Nuclear_base | 0 | 8 | 1,000 |
| Coal_lowcost | 12,089 | 6 | 1,000 |
| Coal_highcost | 12,218 | 6 | 1,000 |
| LNG_CC_low | 41,300 | 4 | 880 |
| LNG_CC_mid | 44,514 | 4 | 550 |
| CHP_mustrun | 30,000 | 6 | 200 |
| LNG_GT_peak | 5,925 | 4 | 110 |
| Oil_peak | 15,000 | 1 | 200 |
| Hydro_fixed | 0 | 1 | 500 |

**adder_max 검증 (startup_cost x 1000 / min_up_time / pmax_unit):**
- LNG_CC_low: 41,300 x 1000 / 4 / 880 = **11,733 원/MWh**
- Coal_lowcost: 12,089 x 1000 / 6 / 1000 = **2,015 원/MWh**

---

### 2.7 `nuclear_must_off.csv` — 원전 계획정비 일정

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료** |
| 행 수 | 18 (2024년 정비 건수) |
| 컬럼 | `id`, `off_start_day`, `off_start_time`, `off_end_day`, `off_end_time` |
| 원본 | `한국수력원자력(주)_원전 호기별 계획예방정비 현황_20250609.csv` |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_nuclear_must_off.py` |

**월별 정비 호기 수 (총 24기 중):**

| 월 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|----|---|---|---|---|---|---|---|---|---|----|----|-----|
| 정비 중 | 3 | 3 | 3 | 3 | 4 | 4 | 5 | 6 | 5 | 2 | 3 | 3 |
| 가용 (기) | 21 | 21 | 21 | 21 | 20 | 20 | 19 | 18 | 19 | 22 | 21 | 21 |
| 가용 Pmax (MW) | 21,000 | 21,000 | 21,000 | 21,000 | 20,000 | 20,000 | 19,000 | 18,000 | 19,000 | 22,000 | 21,000 | 21,000 |

> 7~9월 하절기에 정비 호기가 집중 (최대 6기)

**특이사항:**
- 한수원 공식 데이터 우선 적용 (nuclear_mustoff.csv 대비)
- 날짜는 연중 일수(Day of Year)로 변환, 2024년 범위(1~366)로 클램핑
- 2024년 넘어가는 정비 기간은 12/31까지로 절삭 (월경 2건)

---

### 2.8 `marginal_fuel_counts.csv` — 연료원별 SMP 결정횟수

| 항목 | 내용 |
|------|------|
| 상태 | **실데이터 완료** (월별 → 일별 균등 배분) |
| 행 수 | 366 |
| 컬럼 | `date`, `nuclear`, `coal`, `lng`, `oil`, `other` |
| 원본 | `HOME_전력거래_계통한계가격_연료원별SMP결정.csv` |
| 변환 스크립트 | `scripts/data_format_DATA_SPECIFICATION_marginal_fuel_counts.py` |

**2024년 연간 SMP 결정 비율:**

| 연료 | 연간 시간 수 | 비율 |
|------|-----------|------|
| LNG | 8,399 | 95.6% |
| Coal (유연탄+무연탄) | 558 | 6.4% |
| Nuclear | 5 | 0.06% |
| Oil | 12 | 0.14% |
| Other | 10 | 0.11% |

> LNG가 SMP를 결정하는 시간이 압도적 (95.6%)

**제한사항:**
- 원본이 월별 합산이므로 일별 배분은 균등 분배 적용 (실제 일별 변동 미반영)
- 각 일자의 합계가 정확히 24가 아닐 수 있음 (배분 나머지 처리)

---

## 3. 참조 데이터

`data/reference/` 폴더에 원본 MATPOWER 데이터 보관:
- `KPG193_ver1_5.mat` — MATLAB 바이너리
- `KPG193_ver1_5.m` — MATLAB 스크립트 (193 버스, 122 발전기)

---

## 4. 변환 스크립트 목록

| 스크립트 | 입력 → 출력 |
|---------|-----------|
| `data_format_DATA_SPECIFICATION_smp_demand.py` | EPSIS SMP + KPX 수요 → `smp_demand.csv` |
| `data_format_DATA_SPECIFICATION_renewable.py` | 재생에너지 발전량 검증 및 복사 |
| `data_format_DATA_SPECIFICATION_fuel_costs.py` | EPSIS 연료비용 → `fuel_costs.csv` |
| `data_format_DATA_SPECIFICATION_gencost_genthermal.py` | KPG193 .m → `gencost.csv`, `genthermal.csv` |
| `data_format_DATA_SPECIFICATION_generators.py` | EPSIS 발전기내역 → `generators.csv` |
| `data_format_DATA_SPECIFICATION_nuclear_must_off.py` | 한수원 정비현황 → `nuclear_must_off.csv` |
| `data_format_DATA_SPECIFICATION_marginal_fuel_counts.py` | EPSIS SMP결정 → `marginal_fuel_counts.csv` |

---

## 5. 남은 과제

### 5.1 generators.csv 보완 (우선순위: 높음)

현재 `generators.csv`의 다음 컬럼은 추정값을 사용 중이며, 실데이터 확보 시 정확도가 크게 향상됩니다:

| 보완 항목 | 현재 상태 | 필요한 데이터 소스 |
|----------|----------|-----------------|
| `pmin` | 경험적 비율 적용 | 전력시장운영규칙 기술적 최소출력 |
| `ramp_up/down` | Pmax 비율 추정 | 발전기별 램프율 (전력거래소) |
| `heat_rate` | 교과서적 참조값 | 클러스터별 가중평균 열소비율 |
| `vom` | DATA_SPEC 기본값 | 전력시장운영규칙 변동운영비 |
| CHP 설비용량 | 6,000 MW 추정 | CHP 발전기 별도 분류 정보 |
| Coal 저/고비용 분할 | 50/50 균등 | 개별 석탄발전기 비용 순위 |
| LNG CC/GT 구분 | 60/40 추정 | 복합/단순 가스터빈 분류 |

### 5.2 gencost.csv / genthermal.csv 보완 (우선순위: 중간)

- CHP, Oil, Hydro 3개 클러스터는 KPG193에 미포함 → DATA_SPEC 기본값 유지 중
- KPG193 이외의 MATPOWER 데이터에서 해당 발전기 유형 데이터 확보 시 갱신 가능

### 5.3 marginal_fuel_counts.csv 정밀화 (우선순위: 낮음)

- 현재 월별 → 일별 균등 배분 방식 (검증용이므로 큰 영향 없음)
- 일별 원본 데이터 확보 시 정확도 향상 가능
