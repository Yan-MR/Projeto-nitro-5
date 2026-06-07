param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot "ForcaNitro-Compatibility-Diagnostic.json"
}

$scriptPath = Join-Path $PSScriptRoot "collect_forcanitro_compatibility.ps1"
& $scriptPath -OutputPath $OutputPath
exit $LASTEXITCODE
