# 계산 엔진 API 규격 v1.0 (B ↔ C)

B(AI 분석 API)가 검증된 분석 계획을 계산 요청으로 변환해 C(계산 엔진)에 전달한다.
**실제 계산은 C 엔진에서만 수행**하며, B는 숫자를 만들거나 보정하지 않는다.
스키마 원본: `app/schemas/calc.py` (FastAPI `/openapi.json`에도 노출됨).

## 엔드포인트 (C가 제공)

`POST {CALC_ENGINE_URL}/calculate` — `Content-Type: application/json`

- 성공: HTTP 200, `status: "ok"`
- 엔진이 처리 불가: HTTP 4xx(권장) 또는 200, **본문은 반드시 `status: "error"` + `error` 객체** (HTTP 5xx 본문도 같은 형식 권장)
- `spec_version`은 `"1.0"`

## 요청

| 필드 | 설명 |
|---|---|
| `request_id` | B가 생성. 응답에 그대로 반환해야 함 |
| `dataset_id` | 데이터셋 ID (B의 `CALC_DATASET_ID`, 기본 `commercial_area_v1`) |
| `time_column` | 날짜 컬럼명 (없으면 null) |
| `metrics[]` | `{column, op}` — op: `sum` \| `avg` \| `growth_rate`. column은 숫자 컬럼 |
| `group_by[]` | 그룹 기준 컬럼 (비어 있으면 전체 1행) |
| `filters[]` | `{column, op, value}` — op: `eq` \| `in` \| `gte` \| `lte`. `in`은 value가 리스트, 나머지는 단일 값. 여러 필터는 AND |
| `period` | `{start, end}` `YYYY-MM`, 양끝 포함. `sum`/`avg`에 적용. null이면 전체 기간 |
| `growth` | `growth_rate` 지표가 있을 때만 포함 (아래 참조) |

지역은 별도 필드 없이 `filters`의 `region` 조건으로 전달된다. 업종도 `industry` 필터.

### growth_rate 규칙

```
growth_rate = (current - baseline) / baseline        # 소수 (0.12 = +12%)
current  = 그룹별 sum(column), growth.current_period  (= period)
baseline = 그룹별 sum(column), growth.baseline_period
```

- 기준 기간(`baseline_period`)은 **현재 기간 직전의 같은 길이(개월)** 로 B가 계산해 명시한다.
  예: 현재 2024-01~2024-12 → 기준 2023-01~2023-12 / 현재 2024-02~2024-04 → 기준 2023-11~2024-01
- 기간별 값은 항상 `sum`으로 집계한다 (`growth.aggregation = "sum"`).
- **baseline == 0**: `inf`·0으로 대체하지 말고 값 `null`, 해당 행 `notes`에 `"baseline_zero"` 포함 (current도 0이어도 동일).
- **기준 기간 데이터 없음**: 값 `null` + `notes`에 `"baseline_missing"`.
- `null`은 growth_rate 값에만 허용되며 반드시 `notes` 사유가 있어야 한다. sum/avg에 데이터가 없으면 그룹 행을 만들지 않거나 `NO_DATA` 오류.

## 응답

| 필드 | 설명 |
|---|---|
| `request_id`, `dataset_id` | 요청과 동일해야 함 |
| `status` | `ok` \| `error` |
| `is_mock` | **실제 엔진은 항상 false(생략 가능)**. true면 B가 거부함 |
| `data_version` | 사용한 데이터 버전/적재 시점 (ok일 때 필수) |
| `data_source` | 데이터 출처명 (ok일 때 필수) |
| `rows_used` | 전체 사용 행 수 (필터·기간 적용 후) |
| `methods[]` | 지표별 `{column, op, formula}` — 사람이 읽는 계산식 |
| `applied` | 실제 적용한 조건: `columns_used`, `operations`, `group_by`, `filters`, `period`, `baseline_period` |
| `results[]` | `{group, values, rows_used, notes}`. `group` 키 = `group_by`, `values` 키 = `"<column>.<op>"` |
| `error` | `{code, message, details?}` (status=error일 때 필수) |

### B가 수행하는 응답 검증 (하나라도 어긋나면 502)
- 규격 불일치(필수 필드, 타입), `request_id`/`dataset_id` 불일치
- `applied`의 operations/group_by/filters/period/baseline_period가 요청과 다름
- `columns_used`에 요청 컬럼 누락, 결과 행의 group/values 키가 요청과 다름
- `null` 값이 growth_rate가 아니거나 `notes` 사유가 없음
- 그룹별 `rows_used` 합 > 전체 `rows_used`
- 실제 엔진이 `is_mock=true`로 응답

### 오류 코드
`INVALID_REQUEST`, `DATASET_NOT_FOUND`, `COLUMN_NOT_FOUND`, `UNSUPPORTED_OPERATION`, `NO_DATA`, `INTERNAL_ERROR`

## 예시 1 — 지역 비교 (sum)

요청 (“성수와 홍대의 카페 매출을 비교해줘”)

```json
{
  "spec_version": "1.0",
  "request_id": "9f1c2b7e",
  "dataset_id": "commercial_area_v1",
  "time_column": "year_month",
  "metrics": [{"column": "est_sales", "op": "sum"}],
  "group_by": ["region"],
  "filters": [
    {"column": "industry", "op": "eq", "value": "카페"},
    {"column": "region", "op": "in", "value": ["성수", "홍대"]}
  ],
  "period": null,
  "growth": null
}
```

응답 (숫자는 형식 예시일 뿐 실제 값이 아님)

```json
{
  "spec_version": "1.0",
  "request_id": "9f1c2b7e",
  "status": "ok",
  "is_mock": false,
  "dataset_id": "commercial_area_v1",
  "data_version": "2024-12-01",
  "data_source": "<데이터 출처명>",
  "rows_used": 480,
  "methods": [{"column": "est_sales", "op": "sum", "formula": "sum(est_sales)"}],
  "applied": {
    "columns_used": ["est_sales", "industry", "region"],
    "operations": [{"column": "est_sales", "op": "sum"}],
    "group_by": ["region"],
    "filters": [
      {"column": "industry", "op": "eq", "value": "카페"},
      {"column": "region", "op": "in", "value": ["성수", "홍대"]}
    ],
    "period": null,
    "baseline_period": null
  },
  "results": [
    {"group": {"region": "성수"}, "values": {"est_sales.sum": 0.0}, "rows_used": 240, "notes": []},
    {"group": {"region": "홍대"}, "values": {"est_sales.sum": 0.0}, "rows_used": 240, "notes": []}
  ],
  "error": null
}
```

## 예시 2 — 증감률 (growth_rate)

요청 (“2024년 강남에서 매출이 증가한 업종을 알려줘”)

```json
{
  "spec_version": "1.0",
  "request_id": "a31d0c55",
  "dataset_id": "commercial_area_v1",
  "time_column": "year_month",
  "metrics": [{"column": "est_sales", "op": "growth_rate"}],
  "group_by": ["industry"],
  "filters": [{"column": "region", "op": "eq", "value": "강남"}],
  "period": {"start": "2024-01", "end": "2024-12"},
  "growth": {
    "aggregation": "sum",
    "current_period": {"start": "2024-01", "end": "2024-12"},
    "baseline_period": {"start": "2023-01", "end": "2023-12"},
    "formula": "(current - baseline) / baseline",
    "zero_baseline_policy": "null"
  }
}
```

응답의 `results` 일부 (기준값 0인 업종은 null + 사유)

```json
"methods": [{"column": "est_sales", "op": "growth_rate",
  "formula": "(current - baseline) / baseline; current=sum(est_sales) over current_period, baseline=sum(est_sales) over baseline_period; baseline==0 -> null"}],
"applied": {"...": "...", "period": {"start": "2024-01", "end": "2024-12"},
            "baseline_period": {"start": "2023-01", "end": "2023-12"}},
"results": [
  {"group": {"industry": "카페"}, "values": {"est_sales.growth_rate": 0.0}, "rows_used": 60, "notes": []},
  {"group": {"industry": "의류"}, "values": {"est_sales.growth_rate": null}, "rows_used": 12, "notes": ["baseline_zero"]}
]
```

## 예시 3 — 오류

```json
{
  "spec_version": "1.0",
  "request_id": "a31d0c55",
  "status": "error",
  "dataset_id": "commercial_area_v1",
  "error": {"code": "COLUMN_NOT_FOUND", "message": "컬럼 없음: profit", "details": {"column": "profit"}}
}
```

B는 이를 HTTP 502 `{"error": "calc_engine_error", "engine_error": {...}}`로 전달한다.

## B 쪽 오류 매핑

| 상황 | B 응답 |
|---|---|
| 엔진 연결 불가 | 503 |
| 타임아웃 (`CALC_TIMEOUT_SECONDS`) | 504 |
| 응답이 규격과 다르거나 요청과 불일치 | 502 |
| 엔진이 `status=error` | 502 + `engine_error` |
| 계획 → 요청 변환 불가 (예: growth_rate에 기간 없음) | 422 |
| `CALC_MODE=mock` + `APP_ENV=production` | 503 (Mock 차단) |

## Mock (개발·테스트 전용)

- `CALC_MODE=mock`: `MockCalculator`가 해시로 만든 **가짜 값**을 반환. `is_mock: true`, `data_source: "MOCK_TEST_DATA"`, 각 행 `notes`에 표시, B의 API 응답에 `warning` 포함.
- `APP_ENV=production`에서는 Mock 사용이 차단된다. 실제 엔진 응답에 `is_mock=true`가 있으면 거부한다.
- `CALC_MODE=http`(기본): C 엔진 호출.

## B 쪽 호출 API

- `POST /api/calc` — 분석 계획(`AnalysisPlan`) → 계산 결과
- `POST /api/analyze` — 질문 → 계획 → 계산 (재질문이 필요하면 계산하지 않고 `needs_clarification` 반환)
