"""
generators.csv 생성 (가능한 범위 내에서)
- 입력: HOME_발전설비_발전기세부내역.csv (연료별 설비용량 집계)
         HOME_전력거래_연료비용.csv (평균 연료단가 → marginal_cost 근사)
         HOME_발전·판매_화력발전소열효율.csv (heat_rate 참조)
- 출력: generators.csv (9개 클러스터)

DATA_SPECIFICATION.md 요구:
  name, fuel, pmin, pmax, ramp_up, ramp_down, heat_rate, vom, must_run, marginal_cost
"""
import pandas as pd
import numpy as np
import os

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. 발전기 세부내역에서 연료별 설비용량 집계 ──
df_gen = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_발전설비_발전기세부내역.csv"),
    encoding="cp949"
)

# 컬럼: 사업자, 발전소명, 설비용량, 기, 용량, 해기, 연료, 연료, ...
cols = df_gen.columns.tolist()
print(f"발전기 세부내역 컬럼: {cols}")
print(f"총 발전기 수: {len(df_gen)}")

# 연료 컬럼 (8번째 = index 7)
fuel_col = cols[7]  # '연료'
cap_col = cols[4]   # '용량' (kW)
dispatch_col = cols[16]  # '급전' (중앙/비중앙) - column index 16

print(f"\n연료 컬럼: {fuel_col}")
print(f"용량 컬럼: {cap_col}")

# 중앙급전만 필터 (자가발전 제외)
print(f"\n급전 유형 분포:")
print(df_gen[dispatch_col].value_counts())

df_central = df_gen[df_gen[dispatch_col].astype(str).str.strip() == "중앙"].copy()
print(f"\n중앙급전 발전기: {len(df_central)}")

# 연료별 총 설비용량 (kW → MW)
df_central["용량_MW"] = pd.to_numeric(df_central[cap_col], errors="coerce") / 1000

fuel_capacity = df_central.groupby(fuel_col)["용량_MW"].sum().sort_values(ascending=False)
print("\n중앙급전 연료별 설비용량 (MW):")
print(fuel_capacity)

# ── 2. 9개 클러스터 매핑 ──
# 한국 연료 분류 → 9개 클러스터
# 원자력 → Nuclear_base
# 유연탄 → Coal_lowcost + Coal_highcost (50/50 분할)
# LNG → LNG_CC_low + LNG_CC_mid + LNG_GT_peak (CC:GT 비율 추정)
# 유류 → Oil_peak
# 수력 → Hydro_fixed

# 각 연료별 총 용량 추출
# 연료명 패턴매칭 (인코딩 이슈 방지)
def get_cap(fuel_capacity, patterns):
    total = 0.0
    for fuel_name, cap in fuel_capacity.items():
        for pat in patterns:
            if pat in str(fuel_name):
                total += cap
                break
    return total

nuclear_cap = get_cap(fuel_capacity, ["U"])  # 원자력U
# 원자력U 외에 LNG도 U를 포함하지 않으므로 안전
# 더 정확하게: 연료명에 'U'만 포함하고 LNG/LSWR/LPG는 아닌 것
nuclear_cap = 0.0
lng_extra = 0.0  # 천연U 등 소규모 가스
for fname, cap in fuel_capacity.items():
    fname_s = str(fname).strip()
    # 원자력U만 원전, 천연U는 천연가스(소규모) → LNG에 합산
    if fname_s.endswith("U"):
        if cap > 10000:  # 원전은 대용량 (23950MW)
            nuclear_cap += cap
            print(f"  Nuclear matched: {fname_s} = {cap:.0f} MW")
        else:
            lng_extra += cap
            print(f"  LNG(small gas) matched: {fname_s} = {cap:.0f} MW")

coal_cap = get_cap(fuel_capacity, ["탄"])  # 유연탄, 무연탄, 옥청탄
lng_cap = fuel_capacity.get("LNG", 0) + lng_extra  # 천연U 포함
# 유류/경유 매칭 (유연탄은 '탄'으로 이미 잡혔으므로 제외 필요)
oil_cap = 0.0
for fname, cap in fuel_capacity.items():
    fname_s = str(fname).strip()
    if ("유류" in fname_s or "경유" in fname_s or fname_s == "LSWR" or "LPG" in fname_s):
        oil_cap += cap
        print(f"  Oil matched: {fname_s} = {cap:.0f} MW")
hydro_cap = get_cap(fuel_capacity, ["수"])  # 수력, 양수

# 천연U = 천연가스 소규모 → LNG에 합산하지 않음 (이미 별도)

print(f"\n중앙급전 연료 전체:")
for f, c in fuel_capacity.items():
    print(f"  {f}: {c:.0f} MW")

# CHP는 열병합 - 별도 카테고리
# 소수력, 바이오 등은 제외 (재생에너지로 처리)

total_coal = coal_cap  # get_cap으로 이미 유연탄+무연탄+옥청탄 합산
print(f"\n=== 클러스터별 설비용량 ===")
print(f"원자력: {nuclear_cap:.0f} MW")
print(f"석탄 전체: {total_coal:.0f} MW")
print(f"LNG: {lng_cap:.0f} MW")
print(f"유류: {oil_cap:.0f} MW")
print(f"수력: {hydro_cap:.0f} MW")

# ── 3. 2024년 평균 연료단가로 marginal_cost 근사 ──
df_fuel = pd.read_csv(os.path.join(PROJECT_RAW, "fuel_costs.csv"), encoding="utf-8-sig")
avg_fuel = df_fuel.groupby("fuel")["fuel_cost"].mean()
print(f"\n2024 평균 연료단가 (원/Gcal):")
print(avg_fuel)

# ── 4. 클러스터 정의 ──
# heat_rate: DATA_SPEC 참조 + 화력발전소열효율 참고
# 2024년 열효율: 유연탄 ~34.3%, 무연탄 ~38.6%, LNG ~46.5%
# heat_rate = 860 / (열효율% × 10) [Gcal/MWh] (대략)
# 유연탄: 860/343 ≈ 2.51, LNG CC: 860/465 ≈ 1.85, GT: ~2.5

# Pmin 비율: 원전 75%, 석탄 40%, LNG CC 30%, GT 0%, CHP 의무
# Ramp: 원전 느림, 석탄 중간, LNG 빠름
# VOM: 전력시장운영규칙 참조 수준

clusters = []

# 1. Nuclear_base
hr_nuc = 2.4  # Gcal/MWh (고정)
vom_nuc = 500  # 원/MWh
mc_nuc = hr_nuc * avg_fuel.get("nuclear", 2575) + vom_nuc
clusters.append({
    "name": "Nuclear_base",
    "fuel": "nuclear",
    "pmin": round(nuclear_cap * 0.75),
    "pmax": round(nuclear_cap),
    "ramp_up": 600, "ramp_down": 600,
    "heat_rate": hr_nuc,
    "vom": vom_nuc,
    "must_run": "true",
    "marginal_cost": round(mc_nuc)
})

# 2-3. Coal (50/50 split)
coal_low_cap = round(total_coal * 0.5)
coal_high_cap = total_coal - coal_low_cap

hr_coal_low = 2.1
hr_coal_high = 2.3
vom_coal = 2000
avg_coal_price = avg_fuel.get("coal", 33500)

clusters.append({
    "name": "Coal_lowcost",
    "fuel": "coal",
    "pmin": round(coal_low_cap * 0.4),
    "pmax": coal_low_cap,
    "ramp_up": round(coal_low_cap * 0.12), "ramp_down": round(coal_low_cap * 0.12),
    "heat_rate": hr_coal_low,
    "vom": vom_coal,
    "must_run": "false",
    "marginal_cost": round(hr_coal_low * avg_coal_price + vom_coal)
})

clusters.append({
    "name": "Coal_highcost",
    "fuel": "coal",
    "pmin": round(coal_high_cap * 0.4),
    "pmax": coal_high_cap,
    "ramp_up": round(coal_high_cap * 0.10), "ramp_down": round(coal_high_cap * 0.10),
    "heat_rate": hr_coal_high,
    "vom": 2500,
    "must_run": "false",
    "marginal_cost": round(hr_coal_high * avg_coal_price + 2500)
})

# 4-5. LNG CC (60% of LNG, split 50/50)
lng_cc_total = round(lng_cap * 0.6)
lng_cc_low = round(lng_cc_total * 0.5)
lng_cc_mid = lng_cc_total - lng_cc_low

hr_lng_cc_low = 1.7
hr_lng_cc_mid = 1.8
avg_lng_price = avg_fuel.get("lng", 80000)

clusters.append({
    "name": "LNG_CC_low",
    "fuel": "lng",
    "pmin": round(lng_cc_low * 0.3),
    "pmax": lng_cc_low,
    "ramp_up": round(lng_cc_low * 0.3), "ramp_down": round(lng_cc_low * 0.3),
    "heat_rate": hr_lng_cc_low,
    "vom": 3000,
    "must_run": "false",
    "marginal_cost": round(hr_lng_cc_low * avg_lng_price + 3000)
})

clusters.append({
    "name": "LNG_CC_mid",
    "fuel": "lng",
    "pmin": round(lng_cc_mid * 0.3),
    "pmax": lng_cc_mid,
    "ramp_up": round(lng_cc_mid * 0.3), "ramp_down": round(lng_cc_mid * 0.3),
    "heat_rate": hr_lng_cc_mid,
    "vom": 3500,
    "must_run": "false",
    "marginal_cost": round(hr_lng_cc_mid * avg_lng_price + 3500)
})

# 6. CHP (열병합, must-run)
# 한국 CHP 중앙급전: 약 4000~6000 MW 수준 (추정)
chp_cap = 6000  # MW (별도 카테고리 없으므로 DATA_SPEC 참조값 사용)
clusters.append({
    "name": "CHP_mustrun",
    "fuel": "chp",
    "pmin": 4000,
    "pmax": chp_cap,
    "ramp_up": 1000, "ramp_down": 1000,
    "heat_rate": 2.0,
    "vom": 2000,
    "must_run": "true",
    "marginal_cost": round(2.0 * avg_fuel.get("chp", 70000) + 2000)
})

# 7. LNG GT (나머지 40% of LNG)
lng_gt_cap = lng_cap - lng_cc_total
clusters.append({
    "name": "LNG_GT_peak",
    "fuel": "lng",
    "pmin": 0,
    "pmax": round(lng_gt_cap),
    "ramp_up": round(lng_gt_cap), "ramp_down": round(lng_gt_cap),
    "heat_rate": 2.5,
    "vom": 5000,
    "must_run": "false",
    "marginal_cost": round(2.5 * avg_lng_price + 5000)
})

# 8. Oil_peak
clusters.append({
    "name": "Oil_peak",
    "fuel": "oil",
    "pmin": 0,
    "pmax": round(oil_cap),
    "ramp_up": round(oil_cap), "ramp_down": round(oil_cap),
    "heat_rate": 3.0,
    "vom": 8000,
    "must_run": "false",
    "marginal_cost": round(3.0 * avg_fuel.get("oil", 140000) + 8000)
})

# 9. Hydro_fixed
clusters.append({
    "name": "Hydro_fixed",
    "fuel": "hydro",
    "pmin": 0,
    "pmax": round(hydro_cap),
    "ramp_up": round(hydro_cap), "ramp_down": round(hydro_cap),
    "heat_rate": 0.0,
    "vom": 500,
    "must_run": "false",
    "marginal_cost": 500  # VOM only
})

df_out = pd.DataFrame(clusters)

print("\n=== generators.csv ===")
print(df_out.to_string(index=False))

# ── 5. 검증 ──
total_pmax = df_out["pmax"].sum()
print(f"\n총 설비용량 (Pmax 합계): {total_pmax:,.0f} MW")
print(f"2024 피크수요 참고: ~88,000 MW")
print(f"예비율: {(total_pmax / 88000 - 1) * 100:.1f}%")

# ── 6. 저장 ──
out_project = os.path.join(PROJECT_RAW, "generators.csv")
df_out.to_csv(out_project, index=False)
print(f"\n저장: {out_project}")

out_local = os.path.join(LOCAL_SAVE, "generators.csv")
df_out.to_csv(out_local, index=False)
print(f"저장: {out_local}")

# ── 7. 데이터 부족 사항 보고 ──
print("\n" + "="*60)
print("  generators.csv 데이터 완성도 보고")
print("="*60)

issues = []

print("\n[확보됨 - 실데이터 기반]")
print("  - name, fuel: 9개 클러스터 구성 완료")
print("  - pmax: 발전기세부내역 기반 연료별 총 설비용량 집계")
print("  - marginal_cost: 2024 실제 연료단가 기반 근사 계산")

print("\n[추정값 사용 - 실데이터 보완 필요]")
print("  - pmin: 연료별 경험적 비율 적용 (원전 75%, 석탄 40%, LNG CC 30%)")
print("    -> 발전기별 기술적 최소출력 데이터 필요")
issues.append("pmin: 발전기별 기술적 최소출력 데이터 필요")

print("  - ramp_up/ramp_down: Pmax 비율로 추정")
print("    -> 발전기별 실제 램프율 데이터 필요")
issues.append("ramp_up/down: 발전기별 실제 램프율 데이터 필요")

print("  - heat_rate: DATA_SPEC 참조값 + 열효율통계 간접 추정")
print("    -> 클러스터별 가중평균 열소비율 데이터 필요 (전력시장운영규칙)")
issues.append("heat_rate: 클러스터별 가중평균 열소비율 (전력시장운영규칙) 필요")

print("  - vom: DATA_SPEC 참조값 사용")
print("    -> 전력시장운영규칙 기준 변동운영비 데이터 필요")
issues.append("vom: 전력시장운영규칙 변동운영비 데이터 필요")

print("  - CHP 설비용량: 6000MW (DATA_SPEC 참조)")
print("    -> 발전기세부내역에 CHP 별도 분류 없어 추정치 사용")
issues.append("CHP pmax: 발전기세부내역에 CHP 분류 없음, 실데이터 필요")

print("  - Coal 저비용/고비용 분할: 50/50 임의 분할")
print("    -> 개별 석탄 발전기의 비용 순위 데이터 필요")
issues.append("Coal split: 저비용/고비용 분할 기준 (개별 발전기 비용) 필요")

print("  - LNG CC/GT 비율: 60%/40% 추정")
print("    -> 발전기세부내역에서 CC/GT 구분 필요")
issues.append("LNG CC/GT: 복합/단순 가스터빈 구분 데이터 필요")
