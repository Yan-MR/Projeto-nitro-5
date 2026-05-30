$ErrorActionPreference = "Stop"

$TaskName = "ForcaNitro NitroSense Key Redirect"
$ProjectPath = $PSScriptRoot
$WatcherPath = Join-Path $ProjectPath "nitrosense_key_redirect.ps1"
$ForcaNitroPath = Join-Path $ProjectPath "dist\ForcaNitro.exe"

if (-not (Test-Path $ForcaNitroPath)) {
    throw "ForcaNitro.exe nao encontrado em: $ForcaNitroPath"
}

if (-not (Test-Path $WatcherPath)) {
    throw "Watcher nao encontrado em: $WatcherPath"
}

Remove-Item `
    -Path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\NitroSense.exe" `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue
Remove-Item `
    -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\NitroSense.exe" `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

$userId = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatcherPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal `
    -UserId $userId `
    -LogonType Interactive `
    -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description "Redirects the Acer NitroSense keyboard button to ForcaNitro." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Output "Installed and started task: $TaskName"
