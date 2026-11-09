$ErrorActionPreference = 'Stop'
$app = Join-Path $PSScriptRoot 'dist\VoiceThoughtCapture\VoiceThoughtCapture.exe'
if (-not (Test-Path -LiteralPath $app)) { throw "Application not found: $app" }
$desktop = [Environment]::GetFolderPath('Desktop')
$programs = [Environment]::GetFolderPath('Programs')
$shell = New-Object -ComObject WScript.Shell
foreach ($linkPath in @(
    (Join-Path $desktop 'Voice Thought Capture.lnk'),
    (Join-Path $programs 'Voice Thought Capture.lnk')
)) {
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $app
    $shortcut.WorkingDirectory = Split-Path -Parent $app
    $shortcut.IconLocation = "$app,0"
    $shortcut.Description = 'Capture spoken thoughts to a local UTF-8 note.'
    $shortcut.Save()
}
