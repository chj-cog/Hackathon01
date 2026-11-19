# AIPAL – A: 3D 상권 대시보드

`index.html` 한 파일. 빌드 없이 정적으로 열거나 배포한다 (Vercel이면 Root Directory = `dashboard`).

- 데이터: 서울 열린데이터광장 「상권분석서비스(추정매출-행정동)」 OA-22175, 매출 상위 20곳 (파일 안에 내장)
- 지도: three.js r128, 실제 표고(AWS Terrain Tiles, SRTM 기반, 높이 4배 강조)와 낮은 지대에서 뽑은 한강
- 큰 건물 높이 = 선택한 시간대 매출. 땅 높이는 매출에 더하지 않는다. 작은 건물은 배경 장식

## 로컬에서 보기

```bash
python3 -m http.server 8765 --directory dashboard
```

http://localhost:8765 (API 없이도 동작한다)

## B 분석 API 연결

`상권에 물어보기`에 직접 입력한 질문을 `POST {API}/api/dashboard/analyze` 로 보낸다 (`docs/DASHBOARD_API.md`).

API 주소: 기본값은 `start.ps1` 의 ngrok 주소 (`https://bullion-predefine-phony.ngrok-free.dev`). 그 PC에서 `start.ps1` 이 실행 중이면 그냥 열어도 연결된다. 다른 주소를 쓰려면:

1. 주소창: `http://localhost:8765/?api=http://127.0.0.1:8000` (이 브라우저에 기억됨, `?api=` 로 기본값으로 되돌림, `?api=off` 로 API 끔)
2. `index.html` 의 `<meta name="aipal-api" content="">` 에 주소 입력

| API 응답 | 대시보드 동작 |
|---|---|
| 200 `{area, sql, text}` | 답변 표시, `area` 상권으로 지도 이동 (`geondae` → 대시보드 `kondae` 매핑), `sql` 이 비면 "SQL 없이(pandas) 계산" 표시 |
| 200 + Mock | `테스트용 Mock 데이터 · 실제 분석 결과 아님` 배지 (헤더 `X-Is-Mock` 또는 `text` 접두어로 판단) |
| 422 `needs_clarification` | `clarification_question` 을 그대로 보여줌, 계산 안 함 |
| 401 / 5xx / 연결 실패 / 150초 초과 | 사유를 표시하고, 대시보드 내장 데이터로 답할 수 있는 질문이면 그 답을 "대시보드 데이터로 답했어요" 표시와 함께 보여줌 |

`text` 는 HTML로 해석하지 않고 글자 그대로 넣는다. 아래 예시 질문 버튼은 API를 거치지 않고 내장 데이터로 바로 답한다.

### B 쪽 설정 (서버 `.env`)

- `CORS_ORIGINS` 에 대시보드 주소 추가: 예) `http://localhost:8765,https://<vercel 주소>`
- `X-Is-Mock` 헤더를 브라우저가 읽으려면 `CORSMiddleware(..., expose_headers=["X-Is-Mock","X-Data-Source"])` 필요 (없어도 `text` 접두어로 Mock 표시는 됨)
- ngrok 무료 주소는 브라우저 경고 페이지가 끼므로 대시보드가 `ngrok-skip-browser-warning` 헤더를 보낸다
- `API_KEY` 는 이 페이지에 넣지 않는다. 공개 배포에서 키가 필요하면 Vercel 함수 같은 서버 쪽 프록시가 키를 붙여야 한다
