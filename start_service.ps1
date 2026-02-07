# Start AI Life OS Service
$Env:PYTHONPATH = ".;$Env:PYTHONPATH"
Write-Host "Starting AI Life OS..." -ForegroundColor Green
Write-Host "Frontend served at http://localhost:8010" -ForegroundColor Cyan

python main.py
