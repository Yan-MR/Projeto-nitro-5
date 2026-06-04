$ErrorActionPreference = "SilentlyContinue"

$ProjectPath = $PSScriptRoot
$ForcaNitroPath = Join-Path $ProjectPath "dist\ForcaNitro.exe"
$LogPath = Join-Path $ProjectPath "nitrosense_key_redirect.log"

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class ForcaNitroWindowTools {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

function Write-LaunchLog($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message"
}

$launcherMutex = New-Object System.Threading.Mutex($false, "Local\ForcaNitro.NitroSenseLauncher")
$hasLauncherLock = $false

try {
    try {
        $hasLauncherLock = $launcherMutex.WaitOne([TimeSpan]::FromSeconds(10))
    } catch [System.Threading.AbandonedMutexException] {
        $hasLauncherLock = $true
    }

    if (-not $hasLauncherLock) {
        Write-LaunchLog "Another NitroSense key launcher is still running."
        exit 0
    }

    if (-not (Test-Path $ForcaNitroPath)) {
        Write-LaunchLog "ForcaNitro.exe not found at: $ForcaNitroPath"
        exit 1
    }

    $existingProcesses = @(Get-Process -Name "ForcaNitro")
    $existing = $existingProcesses |
        Where-Object { $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1

    if (-not $existing) {
        $existing = $existingProcesses | Select-Object -First 1
    }

    if ($existing) {
        for ($attempt = 0; $attempt -lt 20 -and $existing.MainWindowHandle -eq 0; $attempt++) {
            Start-Sleep -Milliseconds 100
            $existing.Refresh()
        }

        if ($existing.MainWindowHandle -ne 0) {
            [ForcaNitroWindowTools]::ShowWindow($existing.MainWindowHandle, 9) | Out-Null
            [ForcaNitroWindowTools]::SetForegroundWindow($existing.MainWindowHandle) | Out-Null
            Write-LaunchLog "Focused existing ForcaNitro window (PID $($existing.Id))."
        } else {
            Write-LaunchLog "ForcaNitro is already starting (PID $($existing.Id))."
        }
        exit 0
    }

    Start-Process -FilePath $ForcaNitroPath
    Write-LaunchLog "Started ForcaNitro as administrator after NitroSense key press."
} finally {
    if ($hasLauncherLock) {
        $launcherMutex.ReleaseMutex()
    }
    $launcherMutex.Dispose()
}
