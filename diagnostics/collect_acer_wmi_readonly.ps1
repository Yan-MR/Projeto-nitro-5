param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function ConvertTo-HexString {
    param([UInt64]$InputNumber)
    return "0x{0:X}" -f $InputNumber
}

function Invoke-AcerRead {
    param(
        [Microsoft.Management.Infrastructure.CimInstance]$Instance,
        [string[]]$AvailableMethods,
        [string]$Method,
        [string]$Label,
        [Nullable[UInt32]]$InputValue,
        [ValidateSet("raw", "fanPercent", "sensor", "profile")]
        [string]$Decoder = "raw"
    )

    $result = [ordered]@{
        method       = $Method
        label        = $Label
        inputDecimal = $null
        inputHex     = $null
        success      = $false
        returnValue  = $null
        rawOutput    = $null
        outputHex    = $null
        decoded      = $null
        error        = $null
    }

    if ($Method -notlike "Get*") {
        $result.error = "Blocked: the diagnostic only permits methods whose names start with Get."
        return [pscustomobject]$result
    }

    if ($AvailableMethods -notcontains $Method) {
        $result.error = "Method is not available on this machine."
        return [pscustomobject]$result
    }

    $arguments = @{}
    if ($null -ne $InputValue) {
        $result.inputDecimal = [UInt32]$InputValue
        $result.inputHex = ConvertTo-HexString -InputNumber ([UInt32]$InputValue)
        $arguments.gmInput = [UInt32]$InputValue
    }

    try {
        if ($arguments.Count -gt 0) {
            $response = Invoke-CimMethod -InputObject $Instance -MethodName $Method -Arguments $arguments
        }
        else {
            $response = Invoke-CimMethod -InputObject $Instance -MethodName $Method
        }

        $raw = [UInt64]$response.gmOutput
        $result.success = $true
        $result.returnValue = $response.ReturnValue
        $result.rawOutput = $raw
        $result.outputHex = ConvertTo-HexString -InputNumber $raw

        switch ($Decoder) {
            "fanPercent" {
                $result.decoded = [int](($raw -shr 8) -band 0xFF)
            }
            "sensor" {
                $result.decoded = [int](($raw -shr 8) -band 0xFFFF)
            }
            "profile" {
                $result.decoded = [int](($raw -shr 8) -band 0xFF)
            }
            default {
                $result.decoded = $raw
            }
        }
    }
    catch {
        $result.error = $_.Exception.Message
    }

    return [pscustomobject]$result
}

if (-not (Test-IsAdministrator)) {
    Write-Host ""
    Write-Host "This read-only diagnostic must be run from PowerShell as Administrator." -ForegroundColor Yellow
    Write-Host "It does not change fan settings and does not access the internet."
    Write-Host ""
    exit 1
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot "ForcaNitro-WMI-Diagnostic.json"
}

$computer = Get-CimInstance -ClassName Win32_ComputerSystem
$bios = Get-CimInstance -ClassName Win32_BIOS
$os = Get-CimInstance -ClassName Win32_OperatingSystem

$report = [ordered]@{
    schemaVersion = 1
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    privacy = [ordered]@{
        readOnly = $true
        networkAccess = $false
        includesSerialOrSnid = $false
        note = "The script only invokes known Acer WMI Get methods. The report stays on this computer until the user chooses to share it."
    }
    system = [ordered]@{
        manufacturer = $computer.Manufacturer
        model = $computer.Model
        biosVersion = $bios.SMBIOSBIOSVersion
        osCaption = $os.Caption
        osVersion = $os.Version
    }
    acerGamingFunction = [ordered]@{
        available = $false
        getMethods = @()
        reads = @()
        error = $null
    }
}

try {
    $acerClass = Get-CimClass -Namespace "root/wmi" -ClassName "AcerGamingFunction"
    $acerInstances = @(Get-CimInstance -Namespace "root/wmi" -ClassName "AcerGamingFunction")

    if ($acerInstances.Count -eq 0) {
        throw "AcerGamingFunction exists but no active instance was returned."
    }

    $acer = $acerInstances[0]
    $getMethods = @(
        $acerClass.CimClassMethods |
            ForEach-Object { $_.Name } |
            Where-Object { $_ -like "Get*" } |
            Sort-Object
    )

    $report.acerGamingFunction.available = $true
    $report.acerGamingFunction.getMethods = $getMethods

    $reads = @()
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingFanSpeed" "CPU fan target/readback" ([UInt32]0x01) "fanPercent"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingFanSpeed" "GPU fan target/readback" ([UInt32]0x04) "fanPercent"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingFanBehavior" "CPU fan behavior" ([UInt32]0x01) "raw"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingFanBehavior" "Fan group behavior" ([UInt32]0x03) "raw"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingFanTable" "Fan table" $null "raw"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingMiscSetting" "Supported platform profiles" ([UInt32]0x0A) "raw"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingMiscSetting" "Platform profile" ([UInt32]0x0B) "profile"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "Supported sensor flags" ([UInt32]0x0000) "raw"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "CPU temperature" ([UInt32]0x0101) "sensor"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "CPU fan RPM" ([UInt32]0x0201) "sensor"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "System temperature" ([UInt32]0x0301) "sensor"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "GPU fan RPM" ([UInt32]0x0601) "sensor"
    $reads += Invoke-AcerRead $acer $getMethods "GetGamingSysInfo" "GPU temperature" ([UInt32]0x0A01) "sensor"

    $report.acerGamingFunction.reads = $reads
}
catch {
    $report.acerGamingFunction.error = $_.Exception.Message
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ""
Write-Host "Read-only diagnostic complete." -ForegroundColor Green
Write-Host "Report: $OutputPath"
Write-Host "No Set methods were called and no data was uploaded."
Write-Host ""
