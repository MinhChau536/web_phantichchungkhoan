# ============================================================================
#  Chạy Stock Analytics Pro – tự tạo môi trường ảo & cài thư viện nếu thiếu.
#  Cách dùng (trong PowerShell, tại thư mục GPM1):   .\run_app.ps1
#  Nếu bị chặn chạy script:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# ============================================================================
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$idx = "https://vnstocks.com/api/simple"

if (-not (Test-Path $py)) {
    Write-Host ">>> Chưa có môi trường ảo .venv – đang tạo..." -ForegroundColor Yellow
    python -m venv .venv
}

# Cài thư viện nếu thiếu (lần đầu mất vài phút)
& $py -c "import streamlit, duckdb, plotly, fpdf, pypdf, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Đang cài thư viện từ requirements.txt..." -ForegroundColor Yellow
    & $py -m pip install -r requirements.txt
}
& $py -c "import vnstock" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Đang cài vnstock (bỏ qua gói vẽ biểu đồ vnstock_ezchart không hỗ trợ Python mới)..." -ForegroundColor Yellow
    & $py -m pip install -U vnstock --no-deps --extra-index-url $idx
    & $py -m pip install "vnai>=2.6.0" seaborn psutil "importlib-metadata>=1.0" --extra-index-url $idx
}

& $py -c "import vnstock; print('vnstock', vnstock.__version__)"
Write-Host ">>> Khởi động app tại http://localhost:8501  (Ctrl + C để tắt)" -ForegroundColor Green
& $py -m streamlit run app.py
