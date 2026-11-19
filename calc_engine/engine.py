"""계산 엔진 API 규격 v1.0(docs/CALC_API.md) 구현 + v1.1 확장 제안(docs/CALC_API_v1.1.md).

숫자는 모두 여기서 pandas로 계산한다. 요청에 없는 조건을 더하거나 빼지 않고,
실제로 적용한 조건을 applied에 그대로 돌려준다 (B가 요청과 대조해 검증).
"""
import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from calc_engine.data import (
    DATA_SOURCE,
    DATA_VERSION,
    DATASET_ID,
    DENOMINATORS,
    DIMENSIONS,
    MEASURES,
    TIME_ALIASES,
    UNAVAILABLE,
    industry_groups,
)

V10_OPS = {"sum", "avg", "growth_rate"}
GROWTH_FORMULA = "(current - baseline) / baseline"
NEW_BASIS_FROM = "20241"  # 2024년부터 공간 단위가 표준단위구역으로 바뀜 (docs/DATA.md)


# ---------------- 요청 (B의 v1.0 스키마와 같은 모양, op만 v1.1 확장 포함) ----------------
class Metric(BaseModel):
    column: str
    op: Literal["sum", "avg", "growth_rate", "ratio", "share"]


class Filter(BaseModel):
    column: str
    op: Literal["eq", "in", "gte", "lte"]
    value: str | list[str]


class Period(BaseModel):
    start: str | None = None
    end: str | None = None


class Growth(BaseModel):
    aggregation: Literal["sum"] = "sum"
    current_period: Period
    baseline_period: Period
    formula: Literal["(current - baseline) / baseline"] = GROWTH_FORMULA
    zero_baseline_policy: Literal["null"] = "null"


class CalcRequest(BaseModel):
    spec_version: Literal["1.0", "1.1"] = "1.0"
    request_id: str
    dataset_id: str
    time_column: str | None = None
    metrics: list[Metric] = Field(..., min_length=1)
    group_by: list[str] = []
    filters: list[Filter] = []
    period: Period | None = None
    growth: Growth | None = None


class EngineError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details


HTTP_STATUS = {"DATASET_NOT_FOUND": 404, "NO_DATA": 404, "INTERNAL_ERROR": 500}


# ---------------- 기간·컬럼 해석 ----------------
_YM = re.compile(r"^(\d{4})-(\d{2})$")


def _ym(text: str, field: str) -> tuple[int, int]:
    m = _YM.match(text or "")
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise EngineError("INVALID_REQUEST", f"{field}는 YYYY-MM 형식이어야 합니다: {text}")
    return int(m.group(1)), int(m.group(2))


def quarters_in(period: Period | None, all_quarters: list[str], field: str = "period") -> list[str]:
    """YYYY-MM 기간 → 분기 코드 목록. 데이터가 분기 단위라 분기 경계에 맞는 기간만 받는다."""
    if period is None:
        return list(all_quarters)
    start, end = all_quarters[0], all_quarters[-1]
    if period.start:
        y, m = _ym(period.start, f"{field}.start")
        if m not in (1, 4, 7, 10):
            raise EngineError("INVALID_REQUEST", f"데이터가 분기 단위라 {field}.start는 1·4·7·10월이어야 합니다: {period.start}")
        start = f"{y}{(m - 1) // 3 + 1}"
    if period.end:
        y, m = _ym(period.end, f"{field}.end")
        if m not in (3, 6, 9, 12):
            raise EngineError("INVALID_REQUEST", f"데이터가 분기 단위라 {field}.end는 3·6·9·12월이어야 합니다: {period.end}")
        end = f"{y}{m // 3}"
    if start > end:
        raise EngineError("INVALID_REQUEST", f"{field}의 start가 end보다 늦습니다")
    return [q for q in all_quarters if start <= q <= end]


def _norm_quarter(value: str) -> str:
    """'2025Q4' / '20254' / '2025-10' → '20254'"""
    v = value.strip()
    if re.fullmatch(r"\d{4}Q[1-4]", v):
        return v[:4] + v[5]
    if re.fullmatch(r"\d{4}[1-4]", v):
        return v
    y, m = _ym(v, "분기 값")
    return f"{y}{(m - 1) // 3 + 1}"


def _dimension(name: str) -> str:
    key = TIME_ALIASES.get(name, name)
    if key in DIMENSIONS:
        return DIMENSIONS[key]
    raise _column_error(name)


def _column_error(name: str) -> EngineError:
    if name in UNAVAILABLE:
        return EngineError("COLUMN_NOT_FOUND", UNAVAILABLE[name], {"column": name})
    return EngineError("COLUMN_NOT_FOUND", f"컬럼 없음: {name}", {"column": name})


# ---------------- 계산 ----------------
def _group_sum(frame: pd.DataFrame, gcols: list[str], cols: list[str]) -> dict[tuple, float]:
    s = frame[cols].sum(axis=1)
    if not gcols:
        return {(): float(s.sum())} if len(frame) else {}
    g = s.groupby([frame[c] for c in gcols]).sum()
    return {(k if isinstance(k, tuple) else (k,)): float(v) for k, v in g.items()}


def _group_count(frame: pd.DataFrame, gcols: list[str], col: str | None = None) -> dict[tuple, int]:
    if not gcols:
        return {(): int(frame[col].nunique() if col else len(frame))}
    g = frame.groupby(gcols)
    s = g[col].nunique() if col else g.size()
    return {(k if isinstance(k, tuple) else (k,)): int(v) for k, v in s.items()}


def _formula(m: Metric, source_col: str, denominator: list[str]) -> str:
    if m.op == "sum":
        return f"sum({m.column})"
    if m.op == "avg":
        return f"sum({m.column}) / 기간 내 분기 수 (분기당 평균)"
    if m.op == "share":
        return f"sum({m.column}) / 같은 조건 전체 그룹의 sum({m.column})"
    if m.op == "ratio":
        return f"sum({m.column}) / sum({' + '.join(denominator)})"
    return (f"{GROWTH_FORMULA}; current=sum({m.column}) over current_period, "
            f"baseline=sum({m.column}) over baseline_period; baseline==0 -> null")


def calculate(df: pd.DataFrame, body: dict) -> tuple[int, dict]:
    """요청 본문(dict) → (HTTP 상태, 응답 dict)."""
    request_id = str(body.get("request_id", "")) if isinstance(body, dict) else ""
    dataset_id = str(body.get("dataset_id", "")) if isinstance(body, dict) else ""
    try:
        try:
            req = CalcRequest.model_validate(body)
        except ValidationError as e:
            raise EngineError("INVALID_REQUEST", f"요청 형식이 규격과 다릅니다: {str(e)[:300]}")
        return 200, _calculate(df, req)
    except EngineError as e:
        return HTTP_STATUS.get(e.code, 400), {
            "spec_version": "1.0", "request_id": request_id, "status": "error", "is_mock": False,
            "dataset_id": dataset_id, "error": {"code": e.code, "message": e.message, "details": e.details},
        }
    except Exception as e:  # 예상 못 한 오류도 규격 형식으로 돌려준다
        return 500, {
            "spec_version": "1.0", "request_id": request_id, "status": "error", "is_mock": False,
            "dataset_id": dataset_id, "error": {"code": "INTERNAL_ERROR", "message": f"{type(e).__name__}: {e}"[:300]},
        }


def _calculate(df: pd.DataFrame, req: CalcRequest) -> dict:
    if req.dataset_id != DATASET_ID:
        raise EngineError("DATASET_NOT_FOUND", f"데이터셋 없음: {req.dataset_id}", {"dataset_id": req.dataset_id})

    # 지표 검사
    sources, denominators, families = {}, {}, set()
    for m in req.metrics:
        if m.column not in MEASURES:
            raise _column_error(m.column)
        col, family = MEASURES[m.column]
        sources[m.column], denominators[m.column] = col, DENOMINATORS[family]
        families.add(family)
        if m.op == "growth_rate" and req.growth is None:
            raise EngineError("INVALID_REQUEST", "growth_rate에는 growth(current_period, baseline_period)가 필요합니다")

    gcols = [_dimension(g) for g in req.group_by]
    notes: list[str] = []
    groups = industry_groups(df)

    # 필터 (요청 그대로 적용, 업종 묶음 이름은 실제 업종으로 펼침)
    data = df
    for f in req.filters:
        values = f.value if isinstance(f.value, list) else [f.value]
        if (f.op == "in") != isinstance(f.value, list):
            raise EngineError("INVALID_REQUEST", f"{f.column}: in은 목록, eq·gte·lte는 값 하나여야 합니다")
        if f.column in MEASURES:
            col = MEASURES[f.column][0]
            try:
                nums = [float(v) for v in values]
            except ValueError:
                raise EngineError("INVALID_REQUEST", f"{f.column}: 숫자 값이 필요합니다")
            if f.op == "gte":
                data = data[data[col] >= nums[0]]
            elif f.op == "lte":
                data = data[data[col] <= nums[0]]
            else:
                data = data[data[col].isin(nums)]
            continue
        col = _dimension(f.column)
        if col == "기준_년분기_코드":
            qs = [_norm_quarter(v) for v in values]
            if f.op == "gte":
                data = data[data["기준_년분기_코드"] >= qs[0]]
            elif f.op == "lte":
                data = data[data["기준_년분기_코드"] <= qs[0]]
            else:
                data = data[data["기준_년분기_코드"].isin(qs)]
            continue
        if f.op in ("gte", "lte"):
            raise EngineError("UNSUPPORTED_OPERATION", f"{f.column}에는 gte·lte를 쓸 수 없습니다 (분기·숫자 컬럼만)")
        if f.column == "industry":
            expanded = []
            for v in values:
                if v in groups:
                    expanded += groups[v]
                    notes.append(f"industry_group: {v}={'·'.join(groups[v])}")
                else:
                    expanded.append(v)
            values = expanded
        unknown = sorted(set(values) - set(df[col]))
        if unknown:
            raise EngineError("INVALID_REQUEST", f"지원 범위 밖 값입니다 ({f.column}): {', '.join(unknown)}",
                              {"column": f.column, "values": unknown})
        data = data[data[col].isin(values)]

    all_q = sorted(df["기준_년분기_코드"].unique())
    period_q = quarters_in(req.period, all_q)
    cur = data[data["기준_년분기_코드"].isin(period_q)]
    if cur.empty:
        raise EngineError("NO_DATA", "조건에 맞는 데이터가 없습니다")

    used_q = set(cur["기준_년분기_코드"])
    if req.growth:
        cur_g = data[data["기준_년분기_코드"].isin(quarters_in(req.growth.current_period, all_q, "growth.current_period"))]
        base_q = quarters_in(req.growth.baseline_period, all_q, "growth.baseline_period")
        base_g = data[data["기준_년분기_코드"].isin(base_q)]
        used_q |= set(cur_g["기준_년분기_코드"]) | set(base_g["기준_년분기_코드"])

    # 전체 행에 붙는 안내
    if any(TIME_ALIASES.get(g) for g in req.group_by) or any(TIME_ALIASES.get(f.column) for f in req.filters):
        notes.append("quarter_granularity: 데이터가 분기 단위라 year_month 대신 분기(예: 2025Q4)로 계산했습니다")
    if used_q and min(used_q) < NEW_BASIS_FROM:
        notes.append("pre_2024_basis_unconfirmed: 2024년부터 공간 단위가 바뀌었고 2021~2023년 자료의 재산출 여부는 확인 중입니다")
    if families & {"gender", "age"}:
        notes.append("excludes_corporate_sales: 성별·연령 매출에는 법인 매출이 빠져 있어 비율의 분모는 성별·연령 합계입니다")

    rows_used = _group_count(cur, gcols)
    quarter_n = _group_count(cur, gcols, "기준_년분기_코드")
    dong_n = _group_count(cur, gcols, "행정동_코드") if "지역" in gcols else {}
    values: dict[tuple, dict] = {k: {} for k in rows_used}
    row_notes: dict[tuple, list[str]] = {k: [] for k in rows_used}

    for m in req.metrics:
        key = f"{m.column}.{m.op}"
        s = _group_sum(cur, gcols, [sources[m.column]])
        if m.op == "sum":
            for k in values:
                values[k][key] = s[k]
        elif m.op == "avg":
            for k in values:
                values[k][key] = s[k] / quarter_n[k]
        elif m.op == "share":
            total = sum(s.values())
            for k in values:
                values[k][key] = s[k] / total if total else None
                if not total:
                    row_notes[k].append("denominator_zero")
        elif m.op == "ratio":
            d = _group_sum(cur, gcols, denominators[m.column])
            for k in values:
                values[k][key] = s[k] / d[k] if d.get(k) else None
                if not d.get(k):
                    row_notes[k].append("denominator_zero")
        else:  # growth_rate
            c = _group_sum(cur_g, gcols, [sources[m.column]])
            b = _group_sum(base_g, gcols, [sources[m.column]])
            for k in values:
                if not base_q or k not in b:
                    values[k][key] = None
                    row_notes[k].append("baseline_missing")
                elif b[k] == 0:
                    values[k][key] = None
                    row_notes[k].append("baseline_zero")
                else:
                    values[k][key] = c.get(k, 0.0) / b[k] - 1

    results = []
    for k in sorted(values):
        extra = [f"region_dong_count: {dong_n[k]}"] if k in dong_n else []
        results.append({
            "group": {g: str(v) for g, v in zip(req.group_by, _labels(k, gcols))},
            "values": values[k],
            "rows_used": rows_used[k],
            "notes": row_notes[k] + extra + list(dict.fromkeys(notes)),
        })

    v11 = any(m.op not in V10_OPS for m in req.metrics)
    return {
        "spec_version": "1.1" if v11 else req.spec_version,
        "request_id": req.request_id,
        "status": "ok",
        "is_mock": False,
        "dataset_id": req.dataset_id,
        "data_version": DATA_VERSION,
        "data_source": DATA_SOURCE,
        "rows_used": len(cur),
        "methods": [{"column": m.column, "op": m.op, "formula": _formula(m, sources[m.column], denominators[m.column])}
                    for m in req.metrics],
        "applied": {
            "columns_used": sorted({m.column for m in req.metrics} | set(req.group_by) | {f.column for f in req.filters}),
            "operations": [m.model_dump() for m in req.metrics],
            "group_by": list(req.group_by),
            "filters": [f.model_dump() for f in req.filters],
            "period": req.period.model_dump() if req.period else None,
            "baseline_period": req.growth.baseline_period.model_dump() if req.growth else None,
        },
        "results": results,
        "executed_sql": None,
        "error": None,
    }


def _labels(key: tuple, gcols: list[str]) -> list[str]:
    """분기 묶음은 '2025Q4' 표기로 보여 준다."""
    return [f"{v[:4]}Q{v[4]}" if c == "기준_년분기_코드" else v for c, v in zip(gcols, key)]
