$ErrorActionPreference = "Stop"

$TaskName = "NitroSense"
$ProjectPath = $PSScriptRoot
$BackupPath = Join-Path $ProjectPath "NitroSense.task.backup.xml"
$ForcaNitroPath = Join-Path $ProjectPath "dist\ForcaNitro.exe"
$LauncherPath = Join-Path $ProjectPath "nitrosense_key_launch.ps1"

if (-not (Test-Path $ForcaNitroPath)) {
    throw "ForcaNitro.exe nao encontrado em: $ForcaNitroPath"
}

if (-not (Test-Path $LauncherPath)) {
    throw "Launcher da tecla NitroSense nao encontrado em: $LauncherPath"
}

if (-not (Test-Path $BackupPath)) {
    Export-ScheduledTask -TaskName $TaskName | Set-Content -Path $BackupPath -Encoding Unicode
}

$userId = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$LauncherPath`""
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
    -Principal $principal `
    -Settings $settings `
    -Description "Redirects Acer NitroSense task launches to ForcaNitro." `
    -Force | Out-Null

Write-Output "Task '$TaskName' now points to the ForcaNitro NitroSense key launcher."
Write-Output "Backup saved at: $BackupPath"
