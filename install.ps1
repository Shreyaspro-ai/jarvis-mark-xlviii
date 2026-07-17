# One-time JARVIS setup on Windows.  (Linux/macOS: use ./install.sh instead.)
# After this, Start-Jarvis.bat auto-updates from GitHub on every launch.
#
#   powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot

Write-Host "==> JARVIS (MARK XLVIII) - Windows setup" -ForegroundColor Cyan

# ---- 1. Prerequisites ---------------------------------------------------
function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

if (-not (Have python)) {
  Write-Host "!! Python not found. Install Python 3.12+ from https://python.org (tick 'Add to PATH'), then re-run." -ForegroundColor Red
  exit 1
}
if (-not (Have git)) {
  Write-Host "!! git not found - auto-update won't work. Install from https://git-scm.com" -ForegroundColor Yellow
}
if (-not (Have npm)) {
  Write-Host "!! Node.js/npm not found - the web tools will be skipped. Install from https://nodejs.org" -ForegroundColor Yellow
}

# ---- 2. Virtualenv ------------------------------------------------------
$PY = ".venv\Scripts\python.exe"
if (-not (Test-Path $PY)) {
  Write-Host "==> Creating virtualenv..."
  python -m venv .venv
  if (-not (Test-Path $PY)) { Write-Host "!! venv creation failed" -ForegroundColor Red; exit 1 }
}

Write-Host "==> Installing Python dependencies (a few minutes)..."
& $PY -m pip install -q --upgrade pip
& $PY -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "!! pip install failed" -ForegroundColor Red }
# Needed by JARVIS but not in upstream requirements.txt:
& $PY -m pip install -q PyQt6 truststore

# truststore makes Python trust the Windows cert store - this machine (and many
# corporate ones) sit behind a TLS-inspecting proxy that breaks certifi.
$siteCustomize = ".venv\Lib\site-packages\sitecustomize.py"
if (-not (Test-Path $siteCustomize)) {
  Write-Host "==> Installing sitecustomize.py (TLS via Windows cert store)..."
  @'
# Auto-loaded at Python startup: use the Windows OS certificate store for TLS
# verification instead of certifi's bundle. Verification stays fully enabled.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass
'@ | Set-Content -Encoding UTF8 $siteCustomize
}

# ---- 3. Web tooling -----------------------------------------------------
if (Have npm) {
  Write-Host "==> Installing web tools + Paperclip CLI (npm global)..."
  npm install -g single-file-cli prettier js-beautify paperclipai 2>$null
  if (Test-Path "tools\package.json") {
    Push-Location tools
    npm install --silent 2>$null
    Pop-Location
  }
}

# Scrapy + mitmproxy go in their OWN venv on purpose: mitmproxy pins
# typing-extensions<=4.14 while pydantic (google-genai) needs >=4.14.1, which
# is unresolvable in one environment. JARVIS shells out to them.
Write-Host "==> Installing Scrapy + mitmproxy in an isolated venv..."
& $PY -m venv tools\.venv-web
$WEBPY = "tools\.venv-web\Scripts\python.exe"
if (Test-Path $WEBPY) {
  & $WEBPY -m pip install -q --upgrade pip
  & $WEBPY -m pip install -q scrapy mitmproxy mitmproxy2swagger
  if ($LASTEXITCODE -ne 0) { Write-Host "!! web venv install failed - crawl/intercept unavailable" -ForegroundColor Yellow }
} else {
  Write-Host "!! could not create tools\.venv-web" -ForegroundColor Yellow
}

# ---- 4. API key ---------------------------------------------------------
if (-not (Test-Path "config\api_keys.json")) {
  Copy-Item "config\api_keys.example.json" "config\api_keys.json"
  Write-Host ""
  Write-Host "==> ACTION NEEDED: add your own Gemini API key" -ForegroundColor Yellow
  Write-Host "    Free key: https://aistudio.google.com/apikey"
  Write-Host "    Edit:     config\api_keys.json"
  Write-Host "    (git-ignored - never uploaded.)"
}

Write-Host ""
Write-Host "==> Setup complete." -ForegroundColor Green
Write-Host "    Start JARVIS by double-clicking Start-Jarvis.bat"
Write-Host "    It pulls the latest from GitHub on every launch."
