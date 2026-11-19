"""테스트용 기본 데이터셋 메타데이터 (컬럼 구조만, 실제 수치 없음)."""
from app.schemas.plan import ColumnMeta, DatasetMeta

REGIONS = ["성수", "홍대", "건대", "강남", "이태원"]
INDUSTRIES = ["카페", "음식점", "주점", "편의점", "소매", "의류", "미용"]

# 질문 속 표현 -> 데이터셋 업종 값 (대상 값이 데이터셋에 있을 때만 사용)
INDUSTRY_ALIASES = {
    "커피전문점": "카페", "커피숍": "카페", "커피": "카페",
    "식당": "음식점", "레스토랑": "음식점", "한식": "음식점", "일식": "음식점",
    "중식": "음식점", "양식": "음식점",
    "술집": "주점", "호프": "주점", "이자카야": "주점",
    "소매점": "소매", "옷가게": "의류", "미용실": "미용", "헤어샵": "미용",
}


# 대시보드(A)용 지역 식별값 — 표기는 A와 합의 필요 (docs/DASHBOARD_API.md)
AREA_IDS = {"성수": "seongsu", "홍대": "hongdae", "건대": "geondae", "강남": "gangnam", "이태원": "itaewon"}


def area_ids(regions: list[str]) -> str:
    """단일 지역이면 식별값, 복수면 쉼표 연결(임시안), 없으면 빈 문자열."""
    return ",".join(AREA_IDS[r] for r in regions if r in AREA_IDS)


def default_dataset() -> DatasetMeta:
    return DatasetMeta(
        columns=[
            ColumnMeta(name="region", dtype="string", role="dimension", allowed_values=REGIONS),
            ColumnMeta(name="industry", dtype="string", role="dimension", allowed_values=INDUSTRIES),
            ColumnMeta(name="year_month", dtype="date", role="dimension"),
            ColumnMeta(name="est_sales", dtype="number", role="measure"),
            ColumnMeta(name="store_count", dtype="number", role="measure"),
        ]
    )