$ErrorActionPreference = "Stop"

$AppName = "clawtty-v3"
$InstallDir = Join-Path $env:USERPROFILE ".local\share\$AppName"
$BinDir = Join-Path $env:USERPROFILE ".local\bin"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "ClawTTY v3 — Windows Installer"
Write-Host "--------------------------------"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "Python is required. Install Python 3.10+ and re-run."
}

Write-Host "Installing Python dependencies..."
python -m pip install --user customtkinter>=5.2.0 keyring>=24.0.0 paramiko>=3.4.0 websockets>=12.0 cryptography>=41.0

Write-Host "Installing app files..."
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item (Join-Path $ScriptDir "clawtty.py") $InstallDir -Force
Copy-Item (Join-Path $ScriptDir "src") $InstallDir -Recurse -Force

Write-Host "Creating launcher..."
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
$Launcher = Join-Path $BinDir "clawtty.bat"
@"
@echo off
python "%USERPROFILE%\.local\share\clawtty-v3\clawtty.py" %*
"@ | Out-File -FilePath $Launcher -Encoding ascii -Force

Write-Host ""
Write-Host "Installed: $Launcher"
Write-Host "Add $BinDir to PATH if needed."
Write-Host "Run: clawtty.bat"
