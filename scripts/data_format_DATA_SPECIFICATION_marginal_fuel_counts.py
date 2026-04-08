"""
연료원별 SMP 결정횟수를 DATA_SPECIFICATION.md 형식으로 변환
- 입력: HOME_전력거래_계통한계가격_연료원별SMP결정.csv (월별, 시간 수)
- 출력: marginal_fuel_counts.csv (date, nuclear, coal, lng, oil, other)
  - 원본이 월별이므로 일별로 균등 배분
  - 2024년 366일
"""
import pandas as pd
import os
from calendar import monthrange

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. 원본 데이터 로딩 ──
df_raw = pd.read_csv(
    os.path.join(DATA_DIR, "HOME_전력거래_계통한계가격_연료원별SMP결정.csv"),
    encoding="cp949"
)

cols = [c.strip() for c in df_raw.columns]
df_raw.columns = cols
print(f"컬럼: {cols}")
print(df_raw.head(15))

# 2024년 필터
df_2024 = df_raw[df_raw.iloc[:, 0].astype(str).str.startswith("2024")].copy()
df_2024 = df_2024.sort_values(df_2024.columns[0]).reset_index(drop=True)
print(f"\n2024 months: {len(df_2024)}")

# 컬럼 매핑: LNG, 유류, 유연탄, 무연탄, 원자력, 기타, 합계
# → nuclear, coal(유연탄+무연탄), lng, oil, other(기타)
records = []
for _, row in df_2024.iterrows():
    period = str(row.iloc[0]).strip()  # "2024/01"
    year, month = int(period.split("/")[0]), int(period.split("/")[1])
    days_in_month = monthrange(year, month)[1]

    # 월간 총 시간 수
    lng_total = int(row["LNG"]) if pd.notna(row["LNG"]) else 0
    oil_total = int(row["유류"]) if pd.notna(row["유류"]) else 0

    # 유연탄 + 무연탄 → coal
    coal_total = 0
    if "유연탄" in df_raw.columns:
        coal_total += int(row["유연탄"]) if pd.notna(row["유연탄"]) else 0
    if "무연탄" in df_raw.columns:
        coal_total += int(row["무연탄"]) if pd.notna(row["무연탄"]) else 0

    nuclear_total = int(row["원자력"]) if pd.notna(row["원자력"]) else 0

    other_total = 0
    if "기타" in df_raw.columns:
        other_total += int(row["기타"]) if pd.notna(row["기타"]) else 0

    # 일별로 균등 배분 (정수로 분배, 나머지는 첫째 날에)
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"

        # 균등 배분: 총합 / 일수, 반올림
        def distribute(total, d, days):
            base = total // days
            remainder = total - base * days
            return base + (1 if d <= remainder else 0)

        records.append({
            "date": date_str,
            "nuclear": distribute(nuclear_total, day, days_in_month),
            "coal":    distribute(coal_total, day, days_in_month),
            "lng":     distribute(lng_total, day, days_in_month),
            "oil":     distribute(oil_total, day, days_in_month),
            "other":   distribute(other_total, day, days_in_month),
        })

df_out = pd.DataFrame(records)
print(f"\n총 행 수: {len(df_out)} (기대: 366)")

# 검증: 월별 합산이 원본과 일치하는지
print("\n월별 합산 검증:")
df_out["ym"] = df_out["date"].str[:7]
monthly_check = df_out.groupby("ym")[["nuclear", "coal", "lng", "oil", "other"]].sum()
print(monthly_check)
df_out.drop("ym", axis=1, inplace=True)

# ── 2. 저장 ──
out_project = os.path.join(PROJECT_RAW, "marginal_fuel_counts.csv")
df_out.to_csv(out_project, index=False)
print(f"\n저장: {out_project}")

out_local = os.path.join(LOCAL_SAVE, "marginal_fuel_counts.csv")
df_out.to_csv(out_local, index=False)
print(f"저장: {out_local}")

print("\n=== marginal_fuel_counts.csv 생성 완료 ===")
print(df_out.head(5))
print("...")
print(df_out.tail(5))
