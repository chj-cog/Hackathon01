# 서버(uvicorn) + ngrok 터널을 각각 새 창에서 실행한다.
# 사용: 이 파일을 우클릭 > PowerShell로 실행, 또는 터미널에서 .\start.ps1
$Domain = "bullion-predefine-phony.ngrok-free.dev"
$Root = $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root'; .\.venv\Scripts\python -m uvicorn app.main:app --port 8000"
Start-Sleep 3
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http --url=$Domain 8000"

Write-Host "서버 주소: https://$Domain"
Write-Host "확인: https://$Domain/health"
