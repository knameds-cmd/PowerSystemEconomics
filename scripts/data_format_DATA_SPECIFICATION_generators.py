"""
generators.csv 생성 — 2차 수정
- KPG193 mpc.gen → pmin, pmax (클러스터별 합산 x EPSIS 스케일)
- KPG193 mpc.genthermal → ramp_up, ramp_down
- VOM 제거: 한국 CBP 시장에서는 별도 VOM 항목이 존재하지 않음 (전력시장운영규칙)
- CHP 제거: CHP 발전기는 LNG 등 다른 클러스터에 이미 포함되어 있음
- heat_rate: DATA_SPEC 참조값 유지 (전력시장운영규칙 열소비계수 확보 시 갱신)
- 8개 클러스터 체계
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

# ── 2. 발전기별 데이터 ──
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
        "b": gc[5] * 1000,
        "mc_50": 2 * gc[4] * (g[8] * 0.5) + gc[5] * 1000,
    })

df_all = pd.DataFrame(gens)

# ── 3. 클러스터 배정 ──
coal_median = df_all[df_all["fuel"] == "Coal"]["mc_50"].median()
lng_cc_mask = (df_all["fuel"] == "LNG") & (df_all["pmax"] >= 400)
lng_cc_median = df_all[lng_cc_mask]["mc_50"].median()

def assign_cluster(row):
    fuel, mc, pmax = row["fuel"], row["mc_50"], row["pmax"]
    if fuel == "Nuclear":
        return "Nuclear_base"
    elif fuel == "Coal":
        return "Coal_lowcost" if mc <= coal_median else "Coal_highcost"
    elif fuel == "LNG":
        if pmax >= 400:
            return "LNG_CC_low" if mc <= lng_cc_median else "LNG_CC_mid"
        else:
            return "LNG_GT_peak"
    return "unknown"

df_all["cluster"] = df_all.apply(assign_cluster, axis=1)

# ── 4. 클러스터별 합산 ──
cluster_stats = {}
for name, sub in df_all.groupby("cluster"):
    cluster_stats[name] = {
        "n_units": len(sub),
        "pmax": sub["pmax"].sum(),
        "pmin": sub["pmin"].sum(),
        "ramp_up": sub["ramp_up"].sum(),
        "ramp_down": sub["ramp_down"].sum(),
    }

# ── 5. EPSIS 실제 설비용량 스케일 팩터 ──
df_epsis = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_발전설비_발전기세부내역.csv"), encoding="cp949"
)
cols = df_epsis.columns
df_central = df_epsis[df_epsis[cols[16]].astype(str).str.strip() == "중앙"].copy()
df_central["cap_MW"] = pd.to_numeric(df_central[cols[4]], errors="coerce") / 1000
epsis_cap = {}
for fname, cap in df_central.groupby(cols[7])["cap_MW"].sum().items():
    epsis_cap[str(fname).strip()] = cap

epsis_nuclear, epsis_lng, epsis_coal = 0, 0, 0
for fname, cap in epsis_cap.items():
    if fname.endswith("U") and cap > 10000:
        epsis_nuclear += cap
    elif fname == "LNG":
        epsis_lng += cap
    elif fname.endswith("U") and cap < 10000:
        epsis_lng += cap
    elif "탄" in fname:
        epsis_coal += cap

kpg_nuclear = cluster_stats.get("Nuclear_base", {}).get("pmax", 1)
kpg_coal = sum(cluster_stats.get(c, {}).get("pmax", 0) for c in ["Coal_lowcost", "Coal_highcost"])
kpg_lng = sum(cluster_stats.get(c, {}).get("pmax", 0) for c in ["LNG_CC_low", "LNG_CC_mid", "LNG_GT_peak"])

scale = {
    "nuclear": epsis_nuclear / kpg_nuclear,
    "coal": epsis_coal / kpg_coal,
    "lng": epsis_lng / kpg_lng,
}
print(f"스케일 팩터: Nuclear={scale['nuclear']:.3f}, Coal={scale['coal']:.3f}, LNG={scale['lng']:.3f}")

# ── 6. 2024 연료단가 ──
df_fuel = pd.read_csv(os.path.join(PROJECT_RAW, "fuel_costs.csv"), encoding="utf-8-sig")
avg_fuel = df_fuel.groupby("fuel")["fuel_cost"].mean()

# ── 7. 8개 클러스터 (CHP 제거) ──
# VOM = 0 (한국 CBP 시장에서는 별도 VOM 항목 없음)
# heat_rate: DATA_SPEC 참조값 (전력시장운영규칙 열소비계수 확보 시 갱신)
CLUSTER_ORDER = [
    "Nuclear_base", "Coal_lowcost", "Coal_highcost",
    "LNG_CC_low", "LNG_CC_mid",
    "LNG_GT_peak", "Oil_peak", "Hydro_fixed"
]
FUEL_MAP = {
    "Nuclear_base": "nuclear", "Coal_lowcost": "coal", "Coal_highcost": "coal",
    "LNG_CC_low": "lng", "LNG_CC_mid": "lng",
    "LNG_GT_peak": "lng", "Oil_peak": "oil", "Hydro_fixed": "hydro",
}
HR_REF = {
    "Nuclear_base": 2.4, "Coal_lowcost": 2.1, "Coal_highcost": 2.3,
    "LNG_CC_low": 1.7, "LNG_CC_mid": 1.8,
    "LNG_GT_peak": 2.5, "Oil_peak": 3.0, "Hydro_fixed": 0.0,
}

clusters = []
for cname in CLUSTER_ORDER:
    fuel = FUEL_MAP[cname]
    hr = HR_REF[cname]
    fuel_price = avg_fuel.get(fuel, 0)
    # marginal_cost = HR x FuelPrice (VOM 없음)
    mc = round(hr * fuel_price)

    if cname in cluster_stats:
        s = scale.get(fuel, 1.0)
        stats = cluster_stats[cname]
        pmax = round(stats["pmax"] * s)
        pmin = round(stats["pmin"] * s)
        ramp_up = round(stats["ramp_up"] * s)
        ramp_down = round(stats["ramp_down"] * s)
        must_run = "true" if cname == "Nuclear_base" else "false"
    elif cname == "Oil_peak":
        oil_cap = sum(c for fn, c in epsis_cap.items()
                      if fn in ["LSWR", "LPG*"] or ("유" in fn and "탄" not in fn))
        pmax = round(oil_cap) if oil_cap > 0 else 700
        pmin, ramp_up, ramp_down = 0, pmax, pmax
        must_run = "false"
    elif cname == "Hydro_fixed":
        hydro_cap = sum(c for fn, c in epsis_cap.items() if "수" in fn)
        pmax = round(hydro_cap) if hydro_cap > 0 else 6282
        pmin, ramp_up, ramp_down = 0, pmax, pmax
        must_run = "false"
    else:
        pmax = pmin = ramp_up = ramp_down = 0
        must_run = "false"

    clusters.append({
        "name": cname, "fuel": fuel,
        "pmin": pmin, "pmax": pmax,
        "ramp_up": ramp_up, "ramp_down": ramp_down,
        "heat_rate": hr,
        "vom": 0,  # 한국 CBP 시장: VOM 별도 항목 없음
        "must_run": must_run,
        "marginal_cost": mc,
    })

df_out = pd.DataFrame(clusters)

# ── 8. 출력 ──
print("\n" + "=" * 80)
print("=== generators.csv (2차 수정: VOM 제거, CHP 제거) ===")
print(df_out.to_string(index=False))

total_pmax = df_out["pmax"].sum()
print(f"\n총 Pmax: {total_pmax:,} MW (8개 클러스터)")
print(f"2024 피크수요: ~97,115 MW -> 예비율: {(total_pmax / 97115 - 1) * 100:.1f}%")

print("\n=== 변경사항 (1차 -> 2차) ===")
print("  [삭제] CHP_mustrun 클러스터 (CHP는 LNG 등에 이미 포함)")
print("  [변경] vom: DATA_SPEC 참조값 -> 0 (한국 CBP 시장에서 별도 VOM 없음)")
print("  [변경] marginal_cost: HR x FuelPrice + VOM -> HR x FuelPrice")

# ── 9. 저장 ──
df_out.to_csv(os.path.join(PROJECT_RAW, "generators.csv"), index=False)
df_out.to_csv(os.path.join(LOCAL_SAVE, "generators.csv"), index=False)
print(f"\n저장 완료: generators.csv (8 clusters)")
