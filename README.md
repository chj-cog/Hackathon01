# AIPAL LAB – B: AI 분석 API

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python -m uvicorn app.main:app --reload
.\.venv\Scripts\python -m pytest
```
Docs: http://127.0.0.1:8000/docs

구조: `app/core`(설정) · `app/schemas`(Pydantic) · `app/services`(Ollama/계산엔진 연동 예정) · `app/api/routes`(엔드포인트)