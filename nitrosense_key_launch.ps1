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

if (-not (Test-Path $ForcaNitroPath)) {
    Write-LaunchLog "ForcaNitro.exe not found at: $ForcaNitroPath"
    exit 1
}

$existing = Get-Process -Name "ForcaNitro" |
    Where-Object { $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1

if ($existing) {
    [ForcaNitroWindowTools]::ShowWindow($existing.MainWindowHandle, 9) | Out-Null
    [ForcaNitroWindowTools]::SetForegroundWindow($existing.MainWindowHandle) | Out-Null
    Write-LaunchLog "Focused existing ForcaNitro window (PID $($existing.Id))."
    exit 0
}

Start-Process -FilePath $ForcaNitroPath
Write-LaunchLog "Started ForcaNitro as administrator after NitroSense key press."
