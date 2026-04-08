"""
gencost.csv 및 genthermal.csv 생성 - KPG193_ver1_5.m 파싱
- 122개 발전기를 9개 클러스터로 집계
- gencost: 2차 비용함수 C(P) = a*P^2 + b*P + c → 클러스터별 가중평균
- genthermal: startup_cost, min_up_time, pmax_unit
"""
import re
import numpy as np
import pandas as pd
import os

M_FILE = "C:/Users/kname/Desktop/data/KPG193_ver1_5.m"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. .m 파일 파싱 ──
with open(M_FILE, "r") as f:
    text = f.read()

def parse_matrix(text, name):
    """mpc.xxx = [...]; 행렬 파싱"""
    pattern = rf"mpc\.{name}\s*=\s*\[(.*?)\];"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"mpc.{name} not found")

    rows = []
    fuels = []
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 연료 주석 추출
        fuel_match = re.search(r"%\s*(\S+)", line)
        fuel = fuel_match.group(1) if fuel_match else "unknown"
        fuels.append(fuel)

        # 숫자 추출 (% 이전)
        data_part = line.split("%")[0].replace(";", "").strip()
        vals = [float(x) for x in data_part.split()]
        rows.append(vals)

    return rows, fuels

# mpc.gen: bus Pg Qg Qmax Qmin Vg mBase status Pmax Pmin ...
gen_rows, gen_fuels = parse_matrix(text, "gen")
# mpc.gencost: type startup shutdown n c2 c1 c0
gencost_rows, gc_fuels = parse_matrix(text, "gencost")
# mpc.genthermal: type UT DT inistate initpower ramp_up ramp_down startup_lim shutdown_lim startup1 startup2 startup3 ...
genthermal_rows, gt_fuels = parse_matrix(text, "genthermal")

n_gen = len(gen_rows)
print(f"KPG193 발전기 수: {n_gen}")
print(f"연료 분포: LNG={gen_fuels.count('LNG')}, Coal={gen_fuels.count('Coal')}, Nuclear={gen_fuels.count('Nuclear')}")

# ── 2. 발전기별 데이터 추출 ──
generators = []
for i in range(n_gen):
    g = gen_rows[i]
    gc = gencost_rows[i]
    gt = genthermal_rows[i]

    pmax = g[8]   # Pmax (MW)
    pmin = g[9]   # Pmin (MW)
    fuel = gen_fuels[i]

    # gencost: type=2 polynomial, n=3 → a=gc[4], b=gc[5], c=gc[6]
    # MATPOWER 단위: 1000won(천원) = 1$
    # DATA_SPEC 및 Julia 코드 컨벤션:
    #   a: MATPOWER 원본값 그대로 (MC 기여분 소수)
    #   b: MATPOWER × 1000 (원/MWh)
    #   c: MATPOWER 원본값 그대로 (천원/h, 코드에서 직접 사용)
    a_raw = gc[4]
    b_raw = gc[5]
    c_raw = gc[6]
    startup_cost_raw = gc[1]  # 천원

    # genthermal
    ut = gt[1]   # min up time (h)
    ramp_up = gt[5]  # MW/h

    generators.append({
        "fuel": fuel,
        "pmax": pmax,
        "pmin": pmin,
        "a": a_raw,         # MATPOWER raw (DATA_SPEC 컨벤션)
        "b": b_raw * 1000,  # 원/MWh (천원 → 원)
        "c": c_raw,         # 천원/h (DATA_SPEC 컨벤션, 코드 일치)
        "startup_cost": startup_cost_raw,  # 천원 (DATA_SPEC 단위와 일치)
        "min_up_time": ut,
        "pmax_unit": pmax,  # 개별 호기 정격용량
        "ramp_up": ramp_up,
    })

df_all = pd.DataFrame(generators)
print(f"\n발전기별 데이터 (처음 5개):")
print(df_all.head())

# ── 3. 9개 클러스터 매핑 ──
# Nuclear (25기) → Nuclear_base
# Coal (41기) → marginal_cost 기준 하위 50% = Coal_lowcost, 상위 50% = Coal_highcost
# LNG (56기) → Pmax 기준: CC(대형, Pmax>=400) vs GT(소형, Pmax<400)
#              CC 내에서 비용 기준 하위 50% = LNG_CC_low, 상위 50% = LNG_CC_mid
#              GT = LNG_GT_peak

def assign_cluster(row, coal_threshold, lng_cc_threshold):
    fuel = row["fuel"]
    mc = 2 * row["a"] * (row["pmax"] * 0.5) + row["b"]  # MC at 50% load

    if fuel == "Nuclear":
        return "Nuclear_base"
    elif fuel == "Coal":
        if mc <= coal_threshold:
            return "Coal_lowcost"
        else:
            return "Coal_highcost"
    elif fuel == "LNG":
        if row["pmax"] >= 400:  # CC
            if mc <= lng_cc_threshold:
                return "LNG_CC_low"
            else:
                return "LNG_CC_mid"
        else:
            return "LNG_GT_peak"
    return "unknown"

# MC at 50% load 계산
df_all["mc_50"] = 2 * df_all["a"] * (df_all["pmax"] * 0.5) + df_all["b"]

# Coal 중위수
coal_mask = df_all["fuel"] == "Coal"
coal_median_mc = df_all[coal_mask]["mc_50"].median()
print(f"\nCoal MC 중위수: {coal_median_mc:.0f} 원/MWh")

# LNG CC 중위수 (Pmax >= 400)
lng_cc_mask = (df_all["fuel"] == "LNG") & (df_all["pmax"] >= 400)
lng_cc_median_mc = df_all[lng_cc_mask]["mc_50"].median()
print(f"LNG CC MC 중위수: {lng_cc_median_mc:.0f} 원/MWh")

df_all["cluster"] = df_all.apply(
    lambda r: assign_cluster(r, coal_median_mc, lng_cc_median_mc), axis=1
)

print(f"\n클러스터별 발전기 수:")
print(df_all["cluster"].value_counts().sort_index())

# ── 4. 클러스터별 가중평균 gencost 계산 ──
# C_cluster(P) = a_avg * P^2 + b_avg * P + c_sum
# a_avg: Pmax 가중평균, b_avg: Pmax 가중평균, c_sum: 합산

gencost_results = []
genthermal_results = []

# CHP_mustrun, Oil_peak, Hydro_fixed는 KPG193에 없음 → DATA_SPEC 기본값 유지
CLUSTER_ORDER = [
    "Nuclear_base", "Coal_lowcost", "Coal_highcost",
    "LNG_CC_low", "LNG_CC_mid", "CHP_mustrun",
    "LNG_GT_peak", "Oil_peak", "Hydro_fixed"
]

for cluster_name in CLUSTER_ORDER:
    sub = df_all[df_all["cluster"] == cluster_name]

    if len(sub) == 0:
        # KPG193에 없는 클러스터 → DATA_SPEC 기본값
        defaults_gc = {
            "CHP_mustrun":  {"a": 0.0035,  "b": 80000,  "c": 40000},
            "Oil_peak":     {"a": 0.008,   "b": 210000, "c": 5000},
            "Hydro_fixed":  {"a": 0.0,     "b": 60000,  "c": 0},
        }
        defaults_gt = {
            "CHP_mustrun":  {"startup_cost": 30000,  "min_up_time": 6, "pmax_unit": 200},
            "Oil_peak":     {"startup_cost": 15000,  "min_up_time": 1, "pmax_unit": 200},
            "Hydro_fixed":  {"startup_cost": 0,      "min_up_time": 1, "pmax_unit": 500},
        }
        gc = defaults_gc[cluster_name]
        gencost_results.append({"name": cluster_name, **gc})
        gt = defaults_gt[cluster_name]
        genthermal_results.append({"name": cluster_name, **gt})
        print(f"\n{cluster_name}: DATA_SPEC 기본값 사용 (KPG193에 없음)")
        continue

    # Pmax 가중평균
    weights = sub["pmax"].values
    total_pmax = weights.sum()

    a_avg = np.average(sub["a"].values, weights=weights)
    b_avg = np.average(sub["b"].values, weights=weights)
    c_avg = np.average(sub["c"].values, weights=weights)  # 대표 호기 무부하비 (가중평균)

    gencost_results.append({
        "name": cluster_name,
        "a": round(a_avg, 6),
        "b": round(b_avg, 2),
        "c": round(c_avg, 2),
    })

    # genthermal: 대표 호기 기준
    # startup_cost: Pmax 가중평균 (천원)
    startup_avg = np.average(sub["startup_cost"].values, weights=weights)
    # min_up_time: 최빈값 또는 중위수
    ut_median = sub["min_up_time"].median()
    # pmax_unit: 가장 대표적인(최빈) 호기 용량
    pmax_mode = sub["pmax"].mode().iloc[0] if len(sub["pmax"].mode()) > 0 else sub["pmax"].median()

    genthermal_results.append({
        "name": cluster_name,
        "startup_cost": round(startup_avg, 2),
        "min_up_time": int(ut_median),
        "pmax_unit": round(pmax_mode),
    })

    print(f"\n{cluster_name} ({len(sub)}기, 총 {total_pmax:.0f} MW):")
    print(f"  gencost: a={a_avg:.6f}, b={b_avg:.2f}, c={c_avg:.0f}")
    print(f"  genthermal: startup={startup_avg:.0f} 천원, UT={ut_median:.0f}h, pmax_unit={pmax_mode:.0f} MW")

# ── 5. DataFrame 생성 ──
df_gencost = pd.DataFrame(gencost_results)[["name", "a", "b", "c"]]
df_genthermal = pd.DataFrame(genthermal_results)[["name", "startup_cost", "min_up_time", "pmax_unit"]]

print("\n" + "="*60)
print("=== gencost.csv (KPG193 기반) ===")
print(df_gencost.to_string(index=False))

print("\n=== genthermal.csv (KPG193 기반) ===")
print(df_genthermal.to_string(index=False))

# 검증: MC 범위
print("\n=== MC 검증 (P=Pmax/2 에서) ===")
for _, row in df_gencost.iterrows():
    name = row["name"]
    gen_sub = df_all[df_all["cluster"] == name]
    if len(gen_sub) > 0:
        p_mid = gen_sub["pmax"].sum() / 2
        mc = 2 * row["a"] * p_mid + row["b"]
        print(f"  {name}: MC={mc:.0f} 원/MWh")

# ── 6. 저장 ──
for df, fname in [(df_gencost, "gencost.csv"), (df_genthermal, "genthermal.csv")]:
    out_proj = os.path.join(PROJECT_RAW, fname)
    df.to_csv(out_proj, index=False)
    print(f"\n저장: {out_proj}")

    out_local = os.path.join(LOCAL_SAVE, fname)
    df.to_csv(out_local, index=False)
    print(f"저장: {out_local}")

print("\n=== KPG193 기반 gencost.csv / genthermal.csv 생성 완료 ===")
