param(
    [Parameter(Position=0)]
    [string]$Model
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

function Stop-WithMessage([string]$Message) {
    Write-Host ""
    Write-Host "تعذر تشغيل ISLAM FREE AGENT: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "=== فحص تشغيل ISLAM FREE AGENT ===" -ForegroundColor Cyan

$Tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $Tailscale) { Stop-WithMessage "Tailscale غير مثبت أو غير موجود في PATH." }
try {
    $TsStatus = & $Tailscale.Source status 2>&1
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Tailscale غير متصل. افتح التطبيق وسجّل الدخول ثم أعد المحاولة." }
    $TsIp = (& $Tailscale.Source ip -4 2>$null | Select-Object -First 1).Trim()
    if ($LASTEXITCODE -ne 0 -or $TsIp -notmatch '^100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.(\d{1,3})\.(\d{1,3})$') {
        Stop-WithMessage "لم يتم العثور على عنوان Tailscale IPv4 صالح."
    }
} catch { Stop-WithMessage "تعذر فحص Tailscale: $($_.Exception.Message)" }

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { $Python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $Python) { Stop-WithMessage "Python 3 غير مثبت أو غير موجود في PATH." }
if ($Python.Name -eq "py.exe" -or $Python.Name -eq "py") {
    $PythonVersion = & $Python.Source -3 --version 2>&1
} else {
    $PythonVersion = & $Python.Source --version 2>&1
}
if ($LASTEXITCODE -ne 0 -or "$PythonVersion" -notmatch '^Python 3\\.') {
    Stop-WithMessage "يلزم Python 3؛ النسخة المكتشفة: $PythonVersion"
}

$OpenSSL = Get-Command openssl -ErrorAction SilentlyContinue
if (-not $OpenSSL) { Stop-WithMessage "OpenSSL غير موجود في PATH. ثبّته ثم أعد التشغيل." }

$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $Ollama) { Stop-WithMessage "Ollama غير مثبت أو غير موجود في PATH." }
$Models = & $Ollama.Source list 2>&1
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Ollama لا يستجيب. شغّل Ollama ثم أعد المحاولة." }
Write-Host ""
Write-Host "النماذج المثبتة في Ollama:"
$Models | ForEach-Object { Write-Host "  $_" }

if ([string]::IsNullOrWhiteSpace($Model)) {
    $Model = Read-Host "اكتب اسم النموذج كما يظهر في العمود NAME"
}
if ([string]::IsNullOrWhiteSpace($Model)) { Stop-WithMessage "لم تدخل اسم النموذج." }
$ModelExists = $false
foreach ($Line in $Models) {
    if ($Line -match '^\s*(\S+)\s+' -and $Matches[1] -eq $Model) { $ModelExists = $true; break }
}
if (-not $ModelExists) { Stop-WithMessage "اسم النموذج غير موجود في نتيجة ollama list. انسخه كما يظهر تماماً." }

Write-Host ""
Write-Host "العنوان الخاص للكمبيوتر: $TsIp"
Write-Host "سيبدأ الجسر على HTTPS والمنفذ 8765. لا تغلق هذه النافذة."
Write-Host "سيظهر رمز الاقتران وبصمة الشهادة في هذه الطرفية فقط."
Write-Host "لإيقاف الجسر اضغط Ctrl+C." -ForegroundColor Yellow
Write-Host ""

if ($Python.Name -eq "py.exe" -or $Python.Name -eq "py") {
    & $Python.Source -3 "tools/islam_agent/run_bridge.py" --tailscale --model $Model
} else {
    & $Python.Source "tools/islam_agent/run_bridge.py" --tailscale --model $Model
}
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "انتهى الجسر برمز خطأ $LASTEXITCODE." }
