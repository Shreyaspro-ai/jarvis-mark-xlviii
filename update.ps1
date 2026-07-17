# Pull the latest JARVIS and install anything new. Safe to run anytime.
# Windows counterpart of update.sh. Called automatically by Start-Jarvis.bat.
#
#   powershell -ExecutionPolicy Bypass -File update.ps1 [-Quiet]

param([switch]$Quiet)

$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot

function Say($msg, $colour = "Gray") { if (-not $Quiet) { Write-Host $msg -ForegroundColor $colour } }

if (-not (Test-Path ".git")) {
  Write-Host "!! Not a git clone - can't auto-update. Re-clone from GitHub." -ForegroundColor Red
  exit 1
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Say "!! git not found - skipping update."
  exit 0
}

$PY = ".venv\Scripts\python.exe"
$reqBefore = if (Test-Path "requirements.txt") { (Get-FileHash requirements.txt -Algorithm MD5).Hash } else { "" }
$revBefore = (git rev-parse HEAD 2>$null)

Say ":: Checking for updates..."
git fetch origin main --quiet 2>$null
if ($LASTEXITCODE -ne 0) { Say ":: No network - starting with current version."; exit 0 }

$revRemote = (git rev-parse origin/main 2>$null)
if ($revBefore -eq $revRemote) { Say ":: Already up to date."; exit 0 }

# Never clobber the user's own edits.
git diff --quiet 2>$null; $dirty = ($LASTEXITCODE -ne 0)
git diff --cached --quiet 2>$null; $staged = ($LASTEXITCODE -ne 0)
if ($dirty -or $staged) {
  Write-Host "!! You have local changes to tracked files. Not auto-updating." -ForegroundColor Yellow
  Write-Host "   Run 'git stash' to shelve them, or 'git checkout -- .' to discard, then retry."
  exit 0
}

git merge --ff-only origin/main --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "!! Your branch has diverged from GitHub. Fix manually:  git status" -ForegroundColor Yellow
  exit 0
}

$revAfter = (git rev-parse --short HEAD)
Say (":: Updated {0} -> {1}" -f (git rev-parse --short $revBefore), $revAfter) "Green"
if (-not $Quiet) { git --no-pager log --oneline "$revBefore..HEAD" 2>$null | ForEach-Object { Write-Host "     $_" } }

# Only reinstall when requirements actually changed.
$reqAfter = if (Test-Path "requirements.txt") { (Get-FileHash requirements.txt -Algorithm MD5).Hash } else { "" }
if (($reqBefore -ne $reqAfter) -and (Test-Path $PY)) {
  Say ":: Dependencies changed - installing..."
  # The venv's sitecustomize injects truststore, which makes pip recurse on this
  # kind of machine. Disable it for the install, and always put it back.
  $sc = ".venv\Lib\site-packages\sitecustomize.py"
  $moved = $false
  try {
    if (Test-Path $sc) { Move-Item $sc "$sc.off" -Force; $moved = $true }
    & $PY -m pip install -q -r requirements.txt
  } finally {
    if ($moved -and (Test-Path "$sc.off")) { Move-Item "$sc.off" $sc -Force }
  }
  Say ":: Dependencies up to date."
}

exit 0
