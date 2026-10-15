# ============================================================================
#  Chay Stock Analytics - tu tao moi truong ao .venv va cai thu vien neu thieu.
#  Cach dung (trong PowerShell, tai thu muc GPM1):   .\run_app.ps1
#  Neu bi chan chay script:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#  LUU Y: file nay chi dung ky tu ASCII (khong dau) vi Windows PowerShell 5.1 doc file
#  .ps1 khong co BOM theo bang ma ANSI -> chu tieng Viet co dau lam hong cu phap.
# ============================================================================
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$idx = "https://vnstocks.com/api/simple"

# 1) Tao moi truong ao: uu tien Python 3.12 (neu may co), khong co thi dung python mac dinh
if (-not (Test-Path $py)) {
    Write-Host ">>> Chua co moi truong ao .venv - dang tao..." -ForegroundColor Yellow
    $made = $false
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv 2>$null
        if (Test-Path $py) { $made = $true; Write-Host ">>> Da tao .venv bang Python 3.12" -ForegroundColor Yellow }
    }
    if (-not $made) { python -m venv .venv }
}

# 2) Cai thu vien (TRU vnstock). vnstock keo theo goi vnstock_ezchart doi numpy cu -> tren Python 3.14
#    pip phai bien dich numpy tu ma nguon va LOI ca lan cai. Nen cai vnstock rieng o buoc 3.
& $py -c "import streamlit, duckdb, plotly, fpdf, pypdf, openpyxl, pandas, diskcache, websockets, msgpack" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Dang cai thu vien tu requirements.txt (tru vnstock)..." -ForegroundColor Yellow
    $req = Join-Path $env:TEMP "gpm1_requirements_no_vnstock.txt"
    Get-Content requirements.txt | Where-Object { $_ -notmatch '^\s*vnstock' -and $_ -notmatch '^\s*--extra-index-url' } | Set-Content $req
    & $py -m pip install -r $req
}

# 3) Cai vnstock khong kem goi ve bieu do (vnstock_ezchart), roi cai cac goi vnstock can
& $py -c "import vnstock" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Dang cai vnstock (bo qua goi ve bieu do vnstock_ezchart)..." -ForegroundColor Yellow
    & $py -m pip install -U vnstock --no-deps --extra-index-url $idx
    & $py -m pip install "vnai>=2.6.0" pytz tenacity pydantic beautifulsoup4 openpyxl seaborn psutil "importlib-metadata>=1.0" --extra-index-url $idx
}

& $py -c "import vnstock; print('vnstock', vnstock.__version__)"
& $py -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ">>> Chua cai duoc streamlit - xem loi pip o tren. Thu cai Python 3.12 roi xoa thu muc .venv va chay lai." -ForegroundColor Red
    exit 1
}
Write-Host ">>> Khoi dong app tai http://localhost:8501  (Ctrl + C de tat)" -ForegroundColor Green
& $py -m streamlit run app.py
