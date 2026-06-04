$ErrorActionPreference = "SilentlyContinue"

$ProjectPath = $PSScriptRoot
$LauncherPath = Join-Path $ProjectPath "nitrosense_key_launch.ps1"
$PSLauncherPath = "C:\Program Files\Acer\NitroSense Service\PSLauncher.exe"
$LogPath = Join-Path $ProjectPath "nitrosense_key_redirect.log"

function Write-RedirectLog($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message"
}

function Show-Or-StartForcaNitro {
    if (-not (Test-Path $LauncherPath)) {
        Write-RedirectLog "NitroSense key launcher not found at: $LauncherPath"
        return
    }

    Start-Process `
        -FilePath "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$LauncherPath`"" `
        -WindowStyle Hidden
    Write-RedirectLog "Started NitroSense key launcher."
}

function Ensure-PSAgent {
    $agent = Get-Process -Name "PSAgent" | Select-Object -First 1
    if ($agent) {
        return
    }

    if (Test-Path $PSLauncherPath) {
        Start-Process -FilePath $PSLauncherPath
        Write-RedirectLog "Started Acer PSLauncher to activate NitroSense key listener."
        Start-Sleep -Seconds 2
    } else {
        Write-RedirectLog "PSLauncher not found at: $PSLauncherPath"
    }
}

Write-RedirectLog "NitroSense key redirect watcher started."
Ensure-PSAgent
$lastAgentCheck = Get-Date

while ($true) {
    if (((Get-Date) - $lastAgentCheck).TotalSeconds -ge 20) {
        Ensure-PSAgent
        $lastAgentCheck = Get-Date
    }

    $nitroProcesses = Get-Process -Name "NitroSense"

    foreach ($process in $nitroProcesses) {
        Write-RedirectLog "Detected NitroSense.exe (PID $($process.Id)). Redirecting."
        Stop-Process -Id $process.Id -Force
        Show-Or-StartForcaNitro
    }

    Start-Sleep -Milliseconds 650
}
