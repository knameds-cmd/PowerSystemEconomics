"""
gencost.csv 및 genthermal.csv 생성
- KPG 193 .mat 파일에서 mpc.gencost / mpc.genthermal 추출
- .mat 파일이 없는 경우: DATA_SPECIFICATION.md의 예시값(MATPOWER 참조)으로 기본 생성

사용법:
  python data_format_DATA_SPECIFICATION_gencost_genthermal.py [mat_file_path]

mat_file_path 인자가 없으면 DATA_SPECIFICATION.md의 참조값으로 기본 파일 생성
"""
import pandas as pd
import os
import sys

PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# 9개 클러스터 정의 (DATA_SPECIFICATION.md 참조)
CLUSTER_NAMES = [
    "Nuclear_base", "Coal_lowcost", "Coal_highcost",
    "LNG_CC_low", "LNG_CC_mid", "CHP_mustrun",
    "LNG_GT_peak", "Oil_peak", "Hydro_fixed"
]

def create_from_mat(mat_path):
    """MATPOWER .mat 파일에서 gencost/genthermal 추출"""
    try:
        from scipy.io import loadmat
    except ImportError:
        print("scipy 설치 필요: pip install scipy")
        return False

    data = loadmat(mat_path, squeeze_me=True)

    # mpc 구조체 탐색
    mpc = None
    for key in data:
        if not key.startswith("_"):
            val = data[key]
            if hasattr(val, "dtype") and val.dtype.names:
                if "gencost" in val.dtype.names:
                    mpc = val
                    break

    if mpc is None:
        print(f"WARNING: {mat_path}에서 mpc 구조체를 찾을 수 없습니다.")
        return False

    # gencost 추출
    gencost_raw = mpc["gencost"].item()
    print(f"gencost shape: {gencost_raw.shape}")

    # MATPOWER gencost format: [type, startup, shutdown, n, c_{n-1}, ..., c_0]
    # type=2 (polynomial), n=3 → a, b, c
    gencost_records = []
    for i, row in enumerate(gencost_raw):
        if len(row) >= 7 and row[0] == 2 and row[3] == 3:
            a, b, c = row[4], row[5], row[6]
        else:
            a, b, c = 0.0, 0.0, 0.0
        name = CLUSTER_NAMES[i] if i < len(CLUSTER_NAMES) else f"Gen_{i}"
        gencost_records.append({"name": name, "a": a, "b": b, "c": c})

    df_gencost = pd.DataFrame(gencost_records)

    # genthermal 추출
    if "genthermal" in mpc.dtype.names:
        genthermal_raw = mpc["genthermal"].item()
        print(f"genthermal shape: {genthermal_raw.shape}")

        genthermal_records = []
        for i, row in enumerate(genthermal_raw):
            # [type, UT, DT, inistate, initialpower, ramp_up, ramp_down,
            #  startup_limit, shutdown_limit, startup1, startup2, startup3, ...]
            startup_cost = row[9] if len(row) > 9 else 0.0  # startup1 (천원)
            min_up_time = row[1] if len(row) > 1 else 1.0   # UT
            name = CLUSTER_NAMES[i] if i < len(CLUSTER_NAMES) else f"Gen_{i}"
            genthermal_records.append({
                "name": name,
                "startup_cost": startup_cost,
                "min_up_time": min_up_time,
                "pmax_unit": 500  # placeholder - 실제로는 발전기별 정격용량 필요
            })

        df_genthermal = pd.DataFrame(genthermal_records)
    else:
        print("WARNING: genthermal 데이터 없음")
        df_genthermal = None

    return df_gencost, df_genthermal


def create_default():
    """DATA_SPECIFICATION.md 참조값으로 기본 파일 생성"""
    print("KPG 193 .mat 파일이 없습니다. DATA_SPECIFICATION.md 참조값으로 기본 파일을 생성합니다.")

    # gencost: MATPOWER 참조 + DATA_SPEC 예시
    gencost_data = [
        {"name": "Nuclear_base",  "a": 0.0005,  "b": 12000,  "c": 50000},
        {"name": "Coal_lowcost",  "a": 0.002,   "b": 63000,  "c": 80000},
        {"name": "Coal_highcost", "a": 0.003,   "b": 72000,  "c": 70000},
        {"name": "LNG_CC_low",    "a": 0.004601,"b": 50243,  "c": 5213},
        {"name": "LNG_CC_mid",    "a": 0.0055,  "b": 96500,  "c": 6000},
        {"name": "CHP_mustrun",   "a": 0.0035,  "b": 80000,  "c": 40000},
        {"name": "LNG_GT_peak",   "a": 0.01,    "b": 150000, "c": 3000},
        {"name": "Oil_peak",      "a": 0.008,   "b": 210000, "c": 5000},
        {"name": "Hydro_fixed",   "a": 0.0,     "b": 60000,  "c": 0},
    ]

    # genthermal: MATPOWER 참조 + DATA_SPEC 예시
    genthermal_data = [
        {"name": "Nuclear_base",  "startup_cost": 0,         "min_up_time": 72, "pmax_unit": 1000},
        {"name": "Coal_lowcost",  "startup_cost": 120000,    "min_up_time": 8,  "pmax_unit": 500},
        {"name": "Coal_highcost", "startup_cost": 100000,    "min_up_time": 6,  "pmax_unit": 500},
        {"name": "LNG_CC_low",    "startup_cost": 47398.56,  "min_up_time": 4,  "pmax_unit": 880},
        {"name": "LNG_CC_mid",    "startup_cost": 52138.42,  "min_up_time": 4,  "pmax_unit": 700},
        {"name": "CHP_mustrun",   "startup_cost": 30000,     "min_up_time": 6,  "pmax_unit": 200},
        {"name": "LNG_GT_peak",   "startup_cost": 10000,     "min_up_time": 1,  "pmax_unit": 150},
        {"name": "Oil_peak",      "startup_cost": 15000,     "min_up_time": 1,  "pmax_unit": 200},
        {"name": "Hydro_fixed",   "startup_cost": 0,         "min_up_time": 1,  "pmax_unit": 500},
    ]

    return pd.DataFrame(gencost_data), pd.DataFrame(genthermal_data)


# ── Main ──
if __name__ == "__main__":
    mat_path = sys.argv[1] if len(sys.argv) > 1 else None

    if mat_path and os.path.exists(mat_path):
        result = create_from_mat(mat_path)
        if result is False:
            df_gencost, df_genthermal = create_default()
        else:
            df_gencost, df_genthermal = result
    else:
        df_gencost, df_genthermal = create_default()

    # 저장: gencost.csv
    out1 = os.path.join(PROJECT_RAW, "gencost.csv")
    df_gencost.to_csv(out1, index=False)
    print(f"\n저장: {out1}")
    df_gencost.to_csv(os.path.join(LOCAL_SAVE, "gencost.csv"), index=False)

    print("\n=== gencost.csv ===")
    print(df_gencost.to_string(index=False))

    # 저장: genthermal.csv
    if df_genthermal is not None:
        out2 = os.path.join(PROJECT_RAW, "genthermal.csv")
        df_genthermal.to_csv(out2, index=False)
        print(f"\n저장: {out2}")
        df_genthermal.to_csv(os.path.join(LOCAL_SAVE, "genthermal.csv"), index=False)

        print("\n=== genthermal.csv ===")
        print(df_genthermal.to_string(index=False))

    print("\n⚠️  KPG 193 .mat 파일이 확보되면 이 스크립트를 재실행하세요:")
    print("    python data_format_DATA_SPECIFICATION_gencost_genthermal.py <path_to_kpg193.mat>")
