"""
월별 연료 단가 데이터를 DATA_SPECIFICATION.md 형식으로 변환
- 입력: HOME_전력거래_연료비용.csv (multi-header, 열량단가 섹션 원/Gcal)
- 출력: fuel_costs.csv (year_month, fuel, fuel_cost)
  - 2024년 12개월 × 6개 연료 = 72행
  - 연료: nuclear, coal, lng, oil, chp, hydro
  - 단위: 원/Gcal
"""
import pandas as pd
import os

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. 연료비용 raw 데이터 로딩 ──
# Multi-header CSV: row0=대분류, row1=연료, row2=단위
# 열량단가(원/Gcal) 섹션: columns 6-10 (0-indexed)
df_raw = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_전력거래_연료비용.csv"),
    encoding="cp949",
    header=None
)

print("Raw shape:", df_raw.shape)
print("Header rows:")
print(df_raw.iloc[0, :].tolist())
print(df_raw.iloc[1, :].tolist())
print(df_raw.iloc[2, :].tolist())

# 열량단가(원/Gcal) 컬럼 위치 확인
# row0에서 '열량단가' 찾기
header0 = df_raw.iloc[0, :].astype(str).tolist()
header1 = df_raw.iloc[1, :].astype(str).tolist()
header2 = df_raw.iloc[2, :].astype(str).tolist()

# 열량단가 섹션: 원/Gcal 단위인 컬럼 인덱스 찾기
gcal_cols = {}
for i, (h1, h2) in enumerate(zip(header1, header2)):
    if "Gcal" in str(h2):
        fuel_kr = str(h1).strip()
        gcal_cols[fuel_kr] = i

print(f"\n열량단가(원/Gcal) 컬럼: {gcal_cols}")

# 한글 → 영문 연료 매핑
FUEL_MAP = {
    "원자력": "nuclear",
    "유연탄": "coal",
    "무연탄": "coal",  # 무연탄은 coal에 통합 (유연탄 우선)
    "유류":   "oil",
    "LNG":   "lng",
}

# ── 2. 2024년 데이터 추출 ──
data_rows = df_raw.iloc[3:, :].copy()  # 3행부터 실제 데이터
data_rows = data_rows[data_rows.iloc[:, 0].astype(str).str.startswith("2024")]
data_rows = data_rows.sort_values(0).reset_index(drop=True)

print(f"\n2024 months: {len(data_rows)}")

records = []
for _, row in data_rows.iterrows():
    period = str(row.iloc[0]).strip()  # e.g. "2024/01"
    year_month = period.replace("/", "-")  # → "2024-01"

    for fuel_kr, col_idx in gcal_cols.items():
        val = row.iloc[col_idx]
        try:
            fuel_cost = float(val)
        except:
            fuel_cost = 0.0

        fuel_en = FUEL_MAP.get(fuel_kr)
        if fuel_en is None:
            continue

        # 무연탄은 skip (유연탄을 coal로 사용)
        if fuel_kr == "무연탄":
            continue

        records.append({
            "year_month": year_month,
            "fuel": fuel_en,
            "fuel_cost": round(fuel_cost, 2)
        })

    # chp는 LNG 기반 열병합 → LNG 단가 사용 (DATA_SPEC 참고: chp 40,000~50,000)
    lng_cost = None
    for fuel_kr, col_idx in gcal_cols.items():
        if fuel_kr == "LNG":
            try:
                lng_cost = float(row.iloc[col_idx])
            except:
                lng_cost = 55000.0

    if lng_cost is not None:
        # CHP는 LNG 기반이나 약간 낮은 단가 (열효율 차이) - 약 85% 수준
        chp_cost = round(lng_cost * 0.85, 2)
        records.append({
            "year_month": year_month,
            "fuel": "chp",
            "fuel_cost": chp_cost
        })

    # hydro는 연료비 0
    records.append({
        "year_month": year_month,
        "fuel": "hydro",
        "fuel_cost": 0.0
    })

df_fuel = pd.DataFrame(records)

# 정렬
fuel_order = {"nuclear": 0, "coal": 1, "lng": 2, "oil": 3, "chp": 4, "hydro": 5}
df_fuel["_sort"] = df_fuel["fuel"].map(fuel_order)
df_fuel = df_fuel.sort_values(["year_month", "_sort"]).drop("_sort", axis=1).reset_index(drop=True)

print(f"\n총 행 수: {len(df_fuel)} (기대: 72)")
print(f"\n연료별 행 수:")
print(df_fuel["fuel"].value_counts().sort_index())

# 검증
print(f"\n연료별 단가 범위 (원/Gcal):")
for fuel in ["nuclear", "coal", "lng", "oil", "chp", "hydro"]:
    sub = df_fuel[df_fuel["fuel"] == fuel]
    if len(sub) > 0:
        print(f"  {fuel}: {sub['fuel_cost'].min():.0f} ~ {sub['fuel_cost'].max():.0f}")

# ── 3. 저장 ──
out_project = os.path.join(PROJECT_RAW, "fuel_costs.csv")
df_fuel.to_csv(out_project, index=False, encoding="utf-8-sig")
print(f"\n저장: {out_project}")

out_local = os.path.join(LOCAL_SAVE, "fuel_costs.csv")
df_fuel.to_csv(out_local, index=False, encoding="utf-8-sig")
print(f"저장: {out_local}")

print("\n=== fuel_costs.csv 생성 완료 ===")
print(df_fuel.head(12))
