"""
원전 계획정비 일정을 DATA_SPECIFICATION.md 형식으로 변환
- 입력: 한국수력원자력(주)_원전 호기별 계획예방정비 현황.csv (우선)
         nuclear_mustoff.csv (보조 - 충돌 시 배제)
- 출력: nuclear_must_off.csv (id, off_start_day, off_start_time, off_end_day, off_end_time)
  - 2024년 정비 기간만 추출
  - 날짜를 연중 일수(Day of Year)로 변환
  - 2024년 범위(1~366) 밖의 부분은 클램핑
"""
import pandas as pd
import os
from datetime import datetime, date

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"
LOCAL_SAVE = "C:/Users/kname/Desktop/data"

os.makedirs(PROJECT_RAW, exist_ok=True)

# 2024년 기준일
YEAR = 2024
JAN1 = date(YEAR, 1, 1)
DEC31 = date(YEAR, 12, 31)
MAX_DOY = (DEC31 - JAN1).days + 1  # 366 (윤년)

def date_to_doy(d):
    """날짜 → 연중 일수 (1-based)"""
    return (d - JAN1).days + 1

# ── 1. 한수원 공식 데이터 로딩 ──
for f in os.listdir(DATA_DIR):
    if "수력원자력" in f and f.endswith(".csv"):
        hanwon_path = os.path.join(DATA_DIR, f)
        break

df_hanwon = pd.read_csv(hanwon_path, encoding="cp949")
print(f"한수원 원전 정비 전체: {len(df_hanwon)} rows")
print(f"컬럼: {df_hanwon.columns.tolist()}")

# 컬럼 정리
cols = df_hanwon.columns.tolist()
# 연도, 호기, ?, 시작일, 종료일, 일수
df_hanwon.columns = ["연도", "호기", "차수", "시작일", "종료일", "정비일수"]

# 2024년 필터
df_2024 = df_hanwon[df_hanwon["연도"] == 2024].copy()
print(f"2024년 정비 건수: {len(df_2024)}")
print(df_2024[["호기", "시작일", "종료일"]].to_string())

# 호기명에서 고유 ID 부여
unit_names = sorted(df_2024["호기"].unique())
unit_id_map = {name: i+1 for i, name in enumerate(unit_names)}
print(f"\n호기별 ID 매핑: {unit_id_map}")

# ── 2. 날짜 변환 ──
records = []
for _, row in df_2024.iterrows():
    unit_name = row["호기"]
    unit_id = unit_id_map[unit_name]

    start_date = pd.to_datetime(row["시작일"]).date()
    end_date = pd.to_datetime(row["종료일"]).date()

    # 2024년 범위로 클램핑
    if end_date < JAN1:
        continue  # 2024년 이전에 끝남
    if start_date > DEC31:
        continue  # 2024년 이후에 시작

    eff_start = max(start_date, JAN1)
    eff_end = min(end_date, DEC31)

    off_start_day = date_to_doy(eff_start)
    off_end_day = date_to_doy(eff_end)

    records.append({
        "id": unit_id,
        "off_start_day": off_start_day,
        "off_start_time": 1,
        "off_end_day": off_end_day,
        "off_end_time": 24
    })

df_out = pd.DataFrame(records)
df_out = df_out.sort_values(["off_start_day", "id"]).reset_index(drop=True)

print(f"\n변환 결과: {len(df_out)} rows")
print(df_out.to_string())

# 검증: 월별 정비 호기 수
print("\n월별 정비 호기 수 (대략):")
for month_start_doy, month_name in [(1, "1월"), (32, "2월"), (61, "3월"),
    (92, "4월"), (122, "5월"), (153, "6월"), (183, "7월"),
    (214, "8월"), (245, "9월"), (275, "10월"), (306, "11월"), (336, "12월")]:
    month_mid = month_start_doy + 15
    count = ((df_out["off_start_day"] <= month_mid) & (df_out["off_end_day"] >= month_mid)).sum()
    print(f"  {month_name}: {count}기 정비 중")

# ── 3. 저장 ──
out_project = os.path.join(PROJECT_RAW, "nuclear_must_off.csv")
df_out.to_csv(out_project, index=False)
print(f"\n저장: {out_project}")

out_local = os.path.join(LOCAL_SAVE, "nuclear_must_off_spec.csv")
df_out.to_csv(out_local, index=False)
print(f"저장: {out_local}")

print("\n=== nuclear_must_off.csv 생성 완료 ===")
