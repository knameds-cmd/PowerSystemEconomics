"""
generators.csv 생성 — KPG193 MATPOWER 데이터로 보완 (1차 수정)
- KPG193 mpc.gen → pmin, pmax (클러스터별 합산)
- KPG193 mpc.genthermal → ramp_up, ramp_down (클러스터별 합산)
- KPG193 mpc.gencost → heat_rate 간접 추정 (MC@Pmin ≈ HR x FuelPrice + VOM)
- EPSIS 발전기세부내역 → 실제 한국 설비용량 참고 (스케일 팩터)
- 2024 실제 연료단가 → marginal_cost 산출
"""
import re
import numpy as np
import pandas as pd
import os

M_FILE = "C:/Users/kname/Desktop/data/KPG193_ver1_5.m"
DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. KPG193 파싱 ──
with open(M_FILE, "r") as f:
    text = f.read()

def parse_matrix(text, name):
    pattern = rf"mpc\.{name}\s*=\s*\[(.*?)\];"
    match = re.search(pattern, text, re.DOTALL)
    rows, fuels = [], []
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        fuel_m = re.search(r"%\s*(\S+)", line)
        fuels.append(fuel_m.group(1) if fuel_m else "unknown")
        data = line.split("%")[0].replace(";", "").strip()
        rows.append([float(x) for x in data.split()])
    return rows, fuels

gen_rows, gen_fuels = parse_matrix(text, "gen")
gencost_rows, _ = parse_matrix(text, "gencost")
genthermal_rows, _ = parse_matrix(text, "genthermal")

n_gen = len(gen_rows)
print(f"KPG193 발전기: {n_gen}기 (LNG:{gen_fuels.count('LNG')}, Coal:{gen_fuels.count('Coal')}, Nuclear:{gen_fuels.count('Nuclear')})")

# ── 2. 발전기별 데이터 구조화 ──
gens = []
for i in range(n_gen):
    g = gen_rows[i]
    gc = gencost_rows[i]
    gt = genthermal_rows[i]

    gens.append({
        "fuel": gen_fuels[i],
        "pmax": g[8],
        "pmin": g[9],
        "ramp_up": gt[5],
        "ramp_down": gt[6],
        "a": gc[4],
        "b": gc[5] * 1000,   # 천원/MWh → 원/MWh
        "c": gc[6],
        "startup_cost": gc[1],
        "min_up_time": gt[1],
    })

df_all = pd.DataFrame(gens)

# MC at 50% load
df_all["mc_50"] = 2 * df_all["a"] * (df_all["pmax"] * 0.5) + df_all["b"]

# ── 3. 클러스터 배정 (gencost 스크립트와 동일 기준) ──
coal_mask = df_all["fuel"] == "Coal"
coal_median = df_all[coal_mask]["mc_50"].median()

lng_cc_mask = (df_all["fuel"] == "LNG") & (df_all["pmax"] >= 400)
lng_cc_median = df_all[lng_cc_mask]["mc_50"].median()

def assign_cluster(row):
    fuel = row["fuel"]
    mc = row["mc_50"]
    if fuel == "Nuclear":
        return "Nuclear_base"
    elif fuel == "Coal":
        return "Coal_lowcost" if mc <= coal_median else "Coal_highcost"
    elif fuel == "LNG":
        if row["pmax"] >= 400:
            return "LNG_CC_low" if mc <= lng_cc_median else "LNG_CC_mid"
        else:
            return "LNG_GT_peak"
    return "unknown"

df_all["cluster"] = df_all.apply(assign_cluster, axis=1)

# ── 4. 클러스터별 합산/가중평균 ──
cluster_stats = {}
for name, sub in df_all.groupby("cluster"):
    w = sub["pmax"].values
    cluster_stats[name] = {
        "n_units": len(sub),
        "pmax": sub["pmax"].sum(),
        "pmin": sub["pmin"].sum(),
        "ramp_up": sub["ramp_up"].sum(),
        "ramp_down": sub["ramp_down"].sum(),
        "mc_50_wavg": np.average(sub["mc_50"].values, weights=w),
    }

# ── 5. EPSIS 실제 설비용량으로 스케일링 ──
# KPG193은 특정 시점의 모델 → 실제 2024 한국 설비와 차이 있음
# EPSIS 중앙급전 실데이터를 기준으로 스케일 팩터 적용

df_epsis = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_발전설비_발전기세부내역.csv"),
    encoding="cp949"
)
cols = df_epsis.columns
fuel_col = cols[7]
cap_col = cols[4]
dispatch_col = cols[16]

df_central = df_epsis[df_epsis[dispatch_col].astype(str).str.strip() == "중앙"].copy()
df_central["cap_MW"] = pd.to_numeric(df_central[cap_col], errors="coerce") / 1000

# EPSIS 연료별 총 용량
epsis_cap = {}
for fname, cap in df_central.groupby(fuel_col)["cap_MW"].sum().items():
    epsis_cap[str(fname).strip()] = cap

# EPSIS → 클러스터 매핑
epsis_nuclear = 0
epsis_lng = 0
epsis_coal = 0
for fname, cap in epsis_cap.items():
    if fname.endswith("U") and cap > 10000:
        epsis_nuclear += cap
    elif fname == "LNG":
        epsis_lng += cap
    elif fname.endswith("U") and cap < 10000:
        epsis_lng += cap  # 천연U → LNG 소규모
    elif "탄" in fname:
        epsis_coal += cap

print(f"\nEPSIS 실제 용량: Nuclear={epsis_nuclear:.0f}, Coal={epsis_coal:.0f}, LNG={epsis_lng:.0f} MW")

# KPG193 합산
kpg_nuclear = cluster_stats.get("Nuclear_base", {}).get("pmax", 0)
kpg_coal = sum(cluster_stats.get(c, {}).get("pmax", 0) for c in ["Coal_lowcost", "Coal_highcost"])
kpg_lng = sum(cluster_stats.get(c, {}).get("pmax", 0) for c in ["LNG_CC_low", "LNG_CC_mid", "LNG_GT_peak"])

print(f"KPG193 합산:    Nuclear={kpg_nuclear:.0f}, Coal={kpg_coal:.0f}, LNG={kpg_lng:.0f} MW")

# 스케일 팩터
scale = {
    "nuclear": epsis_nuclear / kpg_nuclear if kpg_nuclear > 0 else 1,
    "coal": epsis_coal / kpg_coal if kpg_coal > 0 else 1,
    "lng": epsis_lng / kpg_lng if kpg_lng > 0 else 1,
}
print(f"스케일 팩터: Nuclear={scale['nuclear']:.3f}, Coal={scale['coal']:.3f}, LNG={scale['lng']:.3f}")

# ── 6. 2024 실제 연료단가 ──
df_fuel = pd.read_csv(os.path.join(PROJECT_RAW, "fuel_costs.csv"), encoding="utf-8-sig")
avg_fuel = df_fuel.groupby("fuel")["fuel_cost"].mean()

# ── 7. 최종 generators.csv 구성 ──
CLUSTER_ORDER = [
    "Nuclear_base", "Coal_lowcost", "Coal_highcost",
    "LNG_CC_low", "LNG_CC_mid", "CHP_mustrun",
    "LNG_GT_peak", "Oil_peak", "Hydro_fixed"
]

FUEL_MAP = {
    "Nuclear_base": "nuclear", "Coal_lowcost": "coal", "Coal_highcost": "coal",
    "LNG_CC_low": "lng", "LNG_CC_mid": "lng", "CHP_mustrun": "chp",
    "LNG_GT_peak": "lng", "Oil_peak": "oil", "Hydro_fixed": "hydro",
}

# heat_rate: KPG193 비용함수는 다른 연료가격 체계로 보정되어 역산 부정확
#           → DATA_SPEC 참조값(한국 발전기 표준) 유지
# vom: 마찬가지로 DATA_SPEC 참조값 유지
HR_REF = {
    "Nuclear_base": 2.4, "Coal_lowcost": 2.1, "Coal_highcost": 2.3,
    "LNG_CC_low": 1.7, "LNG_CC_mid": 1.8, "CHP_mustrun": 2.0,
    "LNG_GT_peak": 2.5, "Oil_peak": 3.0, "Hydro_fixed": 0.0,
}
VOM_REF = {
    "Nuclear_base": 500, "Coal_lowcost": 2000, "Coal_highcost": 2500,
    "LNG_CC_low": 3000, "LNG_CC_mid": 3500, "CHP_mustrun": 2000,
    "LNG_GT_peak": 5000, "Oil_peak": 8000, "Hydro_fixed": 500,
}

# KPG193의 pmin/pmax 비율 (물리적 특성은 스케일에 무관)
kpg_pmin_ratio = {}
for cname, stats in cluster_stats.items():
    kpg_pmin_ratio[cname] = stats["pmin"] / stats["pmax"] if stats["pmax"] > 0 else 0

# KPG193의 ramp/pmax 비율
kpg_ramp_ratio = {}
for cname, stats in cluster_stats.items():
    kpg_ramp_ratio[cname] = {
        "up": stats["ramp_up"] / stats["pmax"] if stats["pmax"] > 0 else 0,
        "down": stats["ramp_down"] / stats["pmax"] if stats["pmax"] > 0 else 0,
    }

clusters = []
for cname in CLUSTER_ORDER:
    fuel = FUEL_MAP[cname]
    vom = VOM_REF[cname]

    if cname in cluster_stats:
        stats = cluster_stats[cname]
        s = scale.get(fuel, 1.0)

        # Pmax: EPSIS 스케일링
        pmax = round(stats["pmax"] * s)
        # Pmin: KPG193 비율 유지 x 스케일링
        pmin = round(stats["pmin"] * s)
        # Ramp: KPG193 비율 유지 x 스케일링
        ramp_up = round(stats["ramp_up"] * s)
        ramp_down = round(stats["ramp_down"] * s)

        # Heat rate: DATA_SPEC 참조값 사용 (KPG193 역산은 부정확)
        hr_est = HR_REF.get(cname, 2.0)

        # must_run: Nuclear과 CHP
        must_run = "true" if cname in ["Nuclear_base", "CHP_mustrun"] else "false"

        # marginal_cost: 실제 연료단가 기반
        fuel_price = avg_fuel.get(fuel, 50000)
        mc = round(hr_est * fuel_price + vom)

    else:
        # KPG193에 없는 클러스터
        if cname == "CHP_mustrun":
            pmax, pmin = 6000, 4000
            ramp_up, ramp_down = 1000, 1000
            hr_est = 2.0
            must_run = "true"
        elif cname == "Oil_peak":
            # EPSIS 유류
            oil_cap = 0
            for fname, cap in epsis_cap.items():
                if fname in ["LSWR", "LPG*"] or "유" in fname:
                    if "탄" not in fname:
                        oil_cap += cap
            pmax = round(oil_cap) if oil_cap > 0 else 700
            pmin = 0
            ramp_up = ramp_down = pmax
            hr_est = 3.0
            must_run = "false"
        elif cname == "Hydro_fixed":
            # EPSIS 수력+양수
            hydro_cap = 0
            for fname, cap in epsis_cap.items():
                if "수" in fname:
                    hydro_cap += cap
            pmax = round(hydro_cap) if hydro_cap > 0 else 6282
            pmin = 0
            ramp_up = ramp_down = pmax
            hr_est = 0.0
            must_run = "false"
        else:
            pmax, pmin = 0, 0
            ramp_up = ramp_down = 0
            hr_est = 0.0
            must_run = "false"

        hr_est = HR_REF.get(cname, 2.0)
        fuel_price = avg_fuel.get(fuel, 0)
        mc = round(hr_est * fuel_price + vom)

    clusters.append({
        "name": cname,
        "fuel": fuel,
        "pmin": pmin,
        "pmax": pmax,
        "ramp_up": ramp_up,
        "ramp_down": ramp_down,
        "heat_rate": hr_est,
        "vom": vom,
        "must_run": must_run,
        "marginal_cost": mc,
    })

df_out = pd.DataFrame(clusters)

# ── 8. 출력 및 검증 ──
print("\n" + "=" * 80)
print("=== generators.csv (KPG193 보완, 1차 수정) ===")
print(df_out.to_string(index=False))

total_pmax = df_out["pmax"].sum()
total_pmin = df_out["pmin"].sum()
print(f"\n총 Pmax: {total_pmax:,} MW")
print(f"총 Pmin: {total_pmin:,} MW")
print(f"2024 피크수요: ~97,115 MW → 예비율: {(total_pmax / 97115 - 1) * 100:.1f}%")

# KPG193 원본 비율 vs 스케일 후 비율 비교
print("\n=== Pmin/Pmax 비율 비교 (KPG193 원본 → 스케일 후) ===")
for cname in CLUSTER_ORDER:
    if cname in cluster_stats:
        orig = kpg_pmin_ratio[cname]
        row = df_out[df_out["name"] == cname].iloc[0]
        actual = row["pmin"] / row["pmax"] if row["pmax"] > 0 else 0
        print(f"  {cname}: KPG193={orig:.2%} → 적용={actual:.2%}")

print("\n=== Ramp/Pmax 비율 (KPG193 기반) ===")
for cname in CLUSTER_ORDER:
    if cname in kpg_ramp_ratio:
        r = kpg_ramp_ratio[cname]
        print(f"  {cname}: ramp_up/Pmax={r['up']:.2%}, ramp_down/Pmax={r['down']:.2%}")

print("\n=== Heat Rate 추정 결과 ===")
for _, row in df_out.iterrows():
    print(f"  {row['name']}: HR={row['heat_rate']:.2f} Gcal/MWh, MC={row['marginal_cost']:,} 원/MWh")

# ── 9. 저장 ──
out_project = os.path.join(PROJECT_RAW, "generators.csv")
df_out.to_csv(out_project, index=False)
print(f"\n저장: {out_project}")

out_local = os.path.join(LOCAL_SAVE, "generators.csv")
df_out.to_csv(out_local, index=False)
print(f"저장: {out_local}")

print("\n=== generators.csv 1차 수정 완료 ===")
