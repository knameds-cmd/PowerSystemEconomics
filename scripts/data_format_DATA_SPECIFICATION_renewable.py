"""
재생에너지 발전량 데이터를 DATA_SPECIFICATION.md 형식으로 확인 및 복사
- 입력: 재생에너지_발전량_2024.csv (이미 올바른 형식)
- 출력: project/data/raw/재생에너지_발전량_2024.csv (형식 검증 후 복사)
  - 컬럼: 날짜, 거래시간, 태양광_합계, 풍력_육지
  - 2024년 8,784행
"""
import pandas as pd
import os
import shutil

DATA_DIR = "C:/Users/kname/Desktop/data"
PROJECT_RAW = "project/data/raw"

os.makedirs(PROJECT_RAW, exist_ok=True)

# ── 1. 형식 검증 ──
src = os.path.join(DATA_DIR, "재생에너지_발전량_2024.csv")
df = pd.read_csv(src, encoding="utf-8")

print(f"컬럼: {df.columns.tolist()}")
print(f"행 수: {len(df)} (기대: 8784)")
print(f"\n태양광 범위: {df['태양광_합계'].min():.2f} ~ {df['태양광_합계'].max():.2f} MW")
print(f"풍력 범위: {df['풍력_육지'].min():.2f} ~ {df['풍력_육지'].max():.2f} MW")
print(f"\n날짜 범위: {df['날짜'].min()} ~ {df['날짜'].max()}")
print(f"거래시간 범위: {df['거래시간'].min()} ~ {df['거래시간'].max()}")

# 결측치 확인
nulls = df.isnull().sum()
print(f"\n결측치: {nulls.to_dict()}")

# ── 2. 복사 (이미 프로젝트에 있을 수 있으나 확인 후 덮어쓰기) ──
dst = os.path.join(PROJECT_RAW, "재생에너지_발전량_2024.csv")
shutil.copy2(src, dst)
print(f"\n복사 완료: {dst}")

print("\n=== 재생에너지_발전량_2024.csv 검증 및 복사 완료 ===")
print(df.head(5))
