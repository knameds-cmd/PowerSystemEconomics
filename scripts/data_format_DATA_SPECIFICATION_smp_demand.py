"""
SMP + 수요 시계열 데이터를 DATA_SPECIFICATION.md 형식으로 변환
- 입력: HOME_전력거래_계통한계가격_시간별SMP.csv (원/kWh, wide)
         한국전력거래소_시간별 전국 전력수요량_20241231.csv (MW, wide)
- 출력: smp_demand.csv (날짜, 거래시간, smp_육지, 수요_육지)
  - SMP: 원/kWh → 원/MWh (×1000)
  - 수요: MW
  - 2024년 366일 × 24시간 = 8,784행
"""
import pandas as pd
import os

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. SMP 데이터 로딩 ──
smp_raw = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_전력거래_계통한계가격_시간별SMP.csv"),
    encoding="cp949"
)
# 컬럼: 기간, 01시, 02시, ..., 24시, 최대, 최소, 가중평균
smp_raw.columns = [c.strip() for c in smp_raw.columns]

# 2024년만 필터
smp_2024 = smp_raw[smp_raw.iloc[:, 0].astype(str).str.startswith("2024")].copy()
smp_2024 = smp_2024.sort_values(smp_2024.columns[0]).reset_index(drop=True)

print(f"SMP 2024 rows (days): {len(smp_2024)}")

# wide → long
smp_records = []
for _, row in smp_2024.iterrows():
    date_str = row.iloc[0]  # e.g. "2024/01/01"
    date_formatted = date_str.replace("/", "-")
    for h in range(1, 25):
        col = f"{h:02d}시"
        smp_kwh = float(row[col])
        smp_mwh = smp_kwh * 1000  # 원/kWh → 원/MWh
        smp_records.append({
            "날짜": date_formatted,
            "거래시간": h,
            "smp_육지": round(smp_mwh, 1)
        })

df_smp = pd.DataFrame(smp_records)
print(f"SMP long rows: {len(df_smp)}")

# ── 2. 수요 데이터 로딩 ──
dem_raw = pd.read_csv(
    os.path.join(DATA_DIR, "한국전력거래소_시간별 전국 전력수요량_20241231.csv"),
    encoding="cp949"
)
dem_raw.columns = [c.strip() for c in dem_raw.columns]

# 2024년만 필터
dem_2024 = dem_raw[dem_raw.iloc[:, 0].astype(str).str.startswith("2024")].copy()
dem_2024 = dem_2024.sort_values(dem_2024.columns[0]).reset_index(drop=True)

print(f"Demand 2024 rows (days): {len(dem_2024)}")

# wide → long
dem_records = []
for _, row in dem_2024.iterrows():
    date_str = row.iloc[0]  # e.g. "2024-01-01"
    date_formatted = str(date_str).replace("/", "-")
    for h in range(1, 25):
        col = f"{h}시"
        demand_mw = float(row[col])
        dem_records.append({
            "날짜": date_formatted,
            "거래시간": h,
            "수요_육지": round(demand_mw, 1)
        })

df_dem = pd.DataFrame(dem_records)
print(f"Demand long rows: {len(df_dem)}")

# ── 3. 병합 ──
df_merged = pd.merge(df_smp, df_dem, on=["날짜", "거래시간"], how="inner")
print(f"Merged rows: {len(df_merged)}")

# 검증
print(f"\nSMP 범위: {df_merged['smp_육지'].min():.1f} ~ {df_merged['smp_육지'].max():.1f} 원/MWh")
print(f"수요 범위: {df_merged['수요_육지'].min():.1f} ~ {df_merged['수요_육지'].max():.1f} MW")

# ── 4. 저장 ──
output_cols = ["날짜", "거래시간", "smp_육지", "수요_육지"]
df_merged = df_merged[output_cols]

# project/data/raw 에 저장
out_project = os.path.join(PROJECT_RAW, "smp_demand.csv")
df_merged.to_csv(out_project, index=False, encoding="utf-8-sig")
print(f"\n저장: {out_project}")

# 로컬 백업
out_local = os.path.join(LOCAL_SAVE, "smp_demand.csv")
df_merged.to_csv(out_local, index=False, encoding="utf-8-sig")
print(f"저장: {out_local}")

print("\n=== smp_demand.csv 생성 완료 ===")
print(df_merged.head(5))
print("...")
print(df_merged.tail(5))
