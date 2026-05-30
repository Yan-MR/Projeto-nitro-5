$ErrorActionPreference = "SilentlyContinue"

$ProjectPath = $PSScriptRoot
$ForcaNitroPath = Join-Path $ProjectPath "dist\ForcaNitro.exe"
$PSLauncherPath = "C:\Program Files\Acer\NitroSense Service\PSLauncher.exe"
$LogPath = Join-Path $ProjectPath "nitrosense_key_redirect.log"

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class WindowTools {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

function Write-RedirectLog($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message"
}

function Show-Or-StartForcaNitro {
    $existing = Get-Process -Name "ForcaNitro" |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1

    if ($existing) {
        [WindowTools]::ShowWindow($existing.MainWindowHandle, 9) | Out-Null
        [WindowTools]::SetForegroundWindow($existing.MainWindowHandle) | Out-Null
        Write-RedirectLog "Focused existing ForcaNitro window (PID $($existing.Id))."
        return
    }

    Start-Process -FilePath $ForcaNitroPath
    Write-RedirectLog "Started ForcaNitro."
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
