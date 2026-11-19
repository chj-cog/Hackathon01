"""원본(행정동 추정매출, 연도별 CSV)에서 region_map.csv의 행정동만 남겨 data/sales_5regions.csv로 저장한다.

원본: 서울 열린데이터광장 OA-22175 '서울시 상권분석서비스(추정매출-행정동)' 2021~2025년 zip을 풀어 calc_engine/raw/ 에 둔다 (git 제외).
사용법: python calc_engine/scripts/build_dataset.py calc_engine/raw/*.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
region_map = pd.read_csv(ROOT / "data" / "region_map.csv", dtype=str)

frames = []
for path in sys.argv[1:]:
    df = pd.read_csv(path, encoding="cp949", dtype={"기준_년분기_코드": str, "행정동_코드": str})
    frames.append(df)
raw = pd.concat(frames, ignore_index=True)

# 이름이 같은 동(예: 신사동)이 있으므로 반드시 코드로 합친다
out = raw.merge(region_map[["지역", "행정동_코드"]], on="행정동_코드", how="inner")
out = out[["지역"] + list(raw.columns)].sort_values(["기준_년분기_코드", "지역", "행정동_코드", "서비스_업종_코드"])

missing = set(region_map["행정동_코드"]) - set(out["행정동_코드"])
if missing:
    sys.exit(f"원본에 없는 행정동 코드: {missing}")

out.to_csv(ROOT / "data" / "sales_5regions.csv", index=False, encoding="utf-8-sig")
print(f"{len(out)}행 저장, 분기 {out['기준_년분기_코드'].min()}~{out['기준_년분기_코드'].max()}")
