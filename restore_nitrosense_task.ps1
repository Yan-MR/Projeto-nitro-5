$ErrorActionPreference = "Stop"

$TaskName = "NitroSense"
$BackupPath = Join-Path $PSScriptRoot "NitroSense.task.backup.xml"

if (-not (Test-Path $BackupPath)) {
    throw "Backup nao encontrado em: $BackupPath"
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Xml (Get-Content -Path $BackupPath -Raw) `
    -Force | Out-Null

Write-Output "Original NitroSense scheduled task restored."
