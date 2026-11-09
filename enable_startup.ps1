$ErrorActionPreference = 'Stop'
$app = Join-Path $PSScriptRoot 'dist\VoiceThoughtCapture\VoiceThoughtCapture.exe'
if (-not (Test-Path -LiteralPath $app)) { throw "Application not found: $app" }
$startup = [Environment]::GetFolderPath('Startup')
$shell = New-Object -ComObject WScript.Shell
$linkPath = Join-Path $startup 'Voice Thought Capture.lnk'
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = $app
$shortcut.WorkingDirectory = Split-Path -Parent $app
$shortcut.IconLocation = "$app,0"
$shortcut.Description = 'Start Voice Thought Capture after sign-in.'
$shortcut.Save()
Write-Host "Startup shortcut created: $linkPath"
