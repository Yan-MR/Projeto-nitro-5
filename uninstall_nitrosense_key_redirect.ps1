$ErrorActionPreference = "SilentlyContinue"

$TaskName = "ForcaNitro NitroSense Key Redirect"
$WatcherPath = Join-Path $PSScriptRoot "nitrosense_key_redirect.ps1"

Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*$WatcherPath*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

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

Write-Output "ForcaNitro NitroSense key redirect removed."
