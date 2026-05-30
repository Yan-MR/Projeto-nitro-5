$ErrorActionPreference = "Stop"

$TaskName = "NitroSense"
$ProjectPath = $PSScriptRoot
$BackupPath = Join-Path $ProjectPath "NitroSense.task.backup.xml"
$ForcaNitroPath = Join-Path $ProjectPath "dist\ForcaNitro.exe"

if (-not (Test-Path $ForcaNitroPath)) {
    throw "ForcaNitro.exe nao encontrado em: $ForcaNitroPath"
}

if (-not (Test-Path $BackupPath)) {
    Export-ScheduledTask -TaskName $TaskName | Set-Content -Path $BackupPath -Encoding Unicode
}

$userId = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $ForcaNitroPath
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

Write-Output "Task '$TaskName' now points to: $ForcaNitroPath"
Write-Output "Backup saved at: $BackupPath"
