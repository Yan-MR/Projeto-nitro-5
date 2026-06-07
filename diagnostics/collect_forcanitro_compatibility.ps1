param(
    [string]$OutputPath,
    [string]$EcProbePath,
    [switch]$SkipEc
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

function ConvertTo-SafeText {
    param($Value)
    if ($null -eq $Value) {
        return $null
    }
    return ([string]$Value).Trim()
}

function Get-FirstNumericOutput {
    param($Response)

    $preferredNames = @("gmOutput", "gfOutput", "gsOutput", "Output", "outValue")
    foreach ($name in $preferredNames) {
        if ($Response.PSObject.Properties.Name -contains $name -and $null -ne $Response.$name) {
            return [ordered]@{
                name = $name
                value = [UInt64]$Response.$name
            }
        }
    }

    foreach ($property in $Response.PSObject.Properties) {
        if ($property.Name -eq "ReturnValue" -or $null -eq $property.Value) {
            continue
        }

        if ($property.Value -is [byte] -or
            $property.Value -is [int16] -or
            $property.Value -is [uint16] -or
            $property.Value -is [int32] -or
            $property.Value -is [uint32] -or
            $property.Value -is [int64] -or
            $property.Value -is [uint64]) {
            return [ordered]@{
                name = $property.Name
                value = [UInt64]$property.Value
            }
        }
    }

    return $null
}

function ConvertTo-AcerMethodInventory {
    param($AcerClass)

    $methods = @()
    foreach ($method in ($AcerClass.CimClassMethods | Sort-Object Name)) {
        $parameters = @()
        foreach ($parameter in $method.Parameters) {
            $parameters += [ordered]@{
                name = $parameter.Name
                cimType = [string]$parameter.CimType
                flags = @($parameter.Flags | ForEach-Object { [string]$_ })
            }
        }

        $methods += [ordered]@{
            name = $method.Name
            startsWithGet = ($method.Name -like "Get*")
            startsWithSet = ($method.Name -like "Set*")
            parameters = $parameters
        }
    }

    return $methods
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
        method = $Method
        label = $Label
        inputDecimal = $null
        inputHex = $null
        success = $false
        returnValue = $null
        outputProperty = $null
        rawOutput = $null
        outputHex = $null
        decoded = $null
        decoder = $Decoder
        error = $null
    }

    if ($Method -notlike "Get*") {
        $result.error = "Blocked: this diagnostic only permits methods whose names start with Get."
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

        $result.returnValue = $response.ReturnValue
        $output = Get-FirstNumericOutput -Response $response
        if ($null -eq $output) {
            $result.error = "The method returned no numeric output property."
            return [pscustomobject]$result
        }

        $raw = [UInt64]$output.value
        $result.success = $true
        $result.outputProperty = $output.name
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

function Resolve-EcProbePath {
    param([string]$RequestedPath)

    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        $candidates += $RequestedPath
    }
    $candidates += "C:\Program Files (x86)\NoteBook FanControl\ec-probe.exe"
    $candidates += "C:\Program Files\NoteBook FanControl\ec-probe.exe"
    $candidates += (Join-Path $PSScriptRoot "ec-probe.exe")
    $candidates += (Join-Path (Split-Path -Parent $PSScriptRoot) "ec-probe.exe")

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

function Invoke-EcProbeRead {
    param(
        [string]$ProbePath,
        [UInt32]$Address,
        [string]$Label,
        [string]$Group
    )

    $addressHex = ConvertTo-HexString -InputNumber $Address
    $result = [ordered]@{
        group = $Group
        label = $Label
        addressDecimal = [UInt32]$Address
        addressHex = $addressHex
        success = $false
        valueDecimal = $null
        valueHex = $null
        rawText = $null
        error = $null
    }

    try {
        $output = & $ProbePath read $addressHex 2>&1
        $exitCode = $LASTEXITCODE
        $text = ($output | Out-String).Trim()
        $result.rawText = $text

        if ($exitCode -ne 0) {
            $result.error = "ec-probe exited with code $exitCode."
            return [pscustomobject]$result
        }

        if ($text -match "^\s*(\d+)\s+\((0x[0-9A-Fa-f]+)\)") {
            $value = [int]$matches[1]
            $result.success = $true
            $result.valueDecimal = $value
            $result.valueHex = ConvertTo-HexString -InputNumber ([UInt32]$value)
        }
        elseif ($text -match "(0x[0-9A-Fa-f]+)") {
            $hex = $matches[1]
            $value = [Convert]::ToInt32($hex, 16)
            $result.success = $true
            $result.valueDecimal = $value
            $result.valueHex = ConvertTo-HexString -InputNumber ([UInt32]$value)
        }
        elseif ($text -match "^\s*(\d+)\s*$") {
            $value = [int]$matches[1]
            $result.success = $true
            $result.valueDecimal = $value
            $result.valueHex = ConvertTo-HexString -InputNumber ([UInt32]$value)
        }
        else {
            $result.error = "Could not parse ec-probe output."
        }
    }
    catch {
        $result.error = $_.Exception.Message
    }

    return [pscustomobject]$result
}

function Get-NvidiaSmiSnapshot {
    $snapshot = [ordered]@{
        available = $false
        path = $null
        query = "temperature.gpu,utilization.gpu,name,driver_version"
        rows = @()
        error = $null
    }

    $command = Get-Command "nvidia-smi.exe" -ErrorAction SilentlyContinue
    if (-not $command) {
        $snapshot.error = "nvidia-smi.exe was not found in PATH."
        return [pscustomobject]$snapshot
    }

    $snapshot.available = $true
    $snapshot.path = $command.Source

    try {
        $output = & $command.Source --query-gpu=temperature.gpu,utilization.gpu,name,driver_version --format=csv,noheader,nounits 2>&1
        if ($LASTEXITCODE -ne 0) {
            $snapshot.error = ($output | Out-String).Trim()
            return [pscustomobject]$snapshot
        }

        foreach ($line in $output) {
            $parts = @($line -split "," | ForEach-Object { $_.Trim() })
            if ($parts.Count -ge 4) {
                $snapshot.rows += [ordered]@{
                    temperatureC = $parts[0]
                    utilizationPercent = $parts[1]
                    name = $parts[2]
                    driverVersion = $parts[3]
                }
            }
        }
    }
    catch {
        $snapshot.error = $_.Exception.Message
    }

    return [pscustomobject]$snapshot
}

if (-not (Test-IsAdministrator)) {
    Write-Host ""
    Write-Host "This read-only diagnostic must be run from PowerShell as Administrator." -ForegroundColor Yellow
    Write-Host "It does not change fan settings, does not call Set* WMI methods, and does not access the internet."
    Write-Host ""
    exit 1
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $PSScriptRoot "ForcaNitro-Compatibility-Diagnostic.json"
}

$computer = Get-CimInstance -ClassName Win32_ComputerSystem
$bios = Get-CimInstance -ClassName Win32_BIOS
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$baseboard = Get-CimInstance -ClassName Win32_BaseBoard

$report = [ordered]@{
    schemaVersion = 2
    diagnosticName = "ForcaNitro Compatibility Diagnostic"
    generatedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    privacy = [ordered]@{
        readOnly = $true
        networkAccess = $false
        ecWrites = $false
        wmiSetMethodsCalled = $false
        includesSerialOrSnid = $false
        includesUserName = $false
        includesPersonalFiles = $false
        note = "This script only lists Acer WMI methods, invokes selected Acer WMI Get* methods, runs selected ec-probe read commands, and optionally queries nvidia-smi. The report stays on this computer until the user chooses to share it."
    }
    system = [ordered]@{
        manufacturer = ConvertTo-SafeText $computer.Manufacturer
        model = ConvertTo-SafeText $computer.Model
        biosVersion = ConvertTo-SafeText $bios.SMBIOSBIOSVersion
        biosManufacturer = ConvertTo-SafeText $bios.Manufacturer
        osCaption = ConvertTo-SafeText $os.Caption
        osVersion = ConvertTo-SafeText $os.Version
        baseboardManufacturer = ConvertTo-SafeText $baseboard.Manufacturer
        baseboardProduct = ConvertTo-SafeText $baseboard.Product
        baseboardVersion = ConvertTo-SafeText $baseboard.Version
    }
    acerGamingFunction = [ordered]@{
        available = $false
        methodInventory = @()
        getMethods = @()
        setMethodsPresentButNotInvoked = @()
        reads = @()
        error = $null
    }
    embeddedController = [ordered]@{
        skipped = [bool]$SkipEc
        ecProbeFound = $false
        ecProbePath = $null
        commandPolicy = "Only ec-probe.exe read is used. No write or dump command is used."
        reads = @()
        error = $null
    }
    nvidiaSmi = $null
}

try {
    $acerClass = Get-CimClass -Namespace "root/wmi" -ClassName "AcerGamingFunction"
    $acerInstances = @(Get-CimInstance -Namespace "root/wmi" -ClassName "AcerGamingFunction")

    if ($acerInstances.Count -eq 0) {
        throw "AcerGamingFunction exists but no active instance was returned."
    }

    $acer = $acerInstances[0]
    $methodInventory = @(ConvertTo-AcerMethodInventory -AcerClass $acerClass)
    $getMethods = @($methodInventory | Where-Object { $_.startsWithGet } | ForEach-Object { $_.name } | Sort-Object)
    $setMethods = @($methodInventory | Where-Object { $_.startsWithSet } | ForEach-Object { $_.name } | Sort-Object)

    $report.acerGamingFunction.available = $true
    $report.acerGamingFunction.methodInventory = $methodInventory
    $report.acerGamingFunction.getMethods = $getMethods
    $report.acerGamingFunction.setMethodsPresentButNotInvoked = $setMethods

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

if (-not $SkipEc) {
    $resolvedEcProbePath = Resolve-EcProbePath -RequestedPath $EcProbePath
    if ($null -eq $resolvedEcProbePath) {
        $report.embeddedController.error = "ec-probe.exe was not found. Install NoteBook FanControl or pass -EcProbePath."
    }
    else {
        $report.embeddedController.ecProbeFound = $true
        $report.embeddedController.ecProbePath = $resolvedEcProbePath

        $ecReads = @()
        $knownAddresses = @(
            @{ address = 0x03; label = "known unlock/control register" },
            @{ address = 0x13; label = "known CPU fan RPM low/byte register on AN515-58" },
            @{ address = 0x14; label = "known CPU fan RPM high/byte register on AN515-58" },
            @{ address = 0x15; label = "known GPU fan RPM low/byte register on AN515-58" },
            @{ address = 0x16; label = "known GPU fan RPM high/byte register on AN515-58" },
            @{ address = 0x21; label = "known fan mode register on AN515-58" },
            @{ address = 0x22; label = "known fan mode register on AN515-58" },
            @{ address = 0x37; label = "known CPU fan target register on AN515-58" },
            @{ address = 0x3A; label = "known GPU fan target register on AN515-58" }
        )

        foreach ($item in $knownAddresses) {
            $ecReads += Invoke-EcProbeRead -ProbePath $resolvedEcProbePath -Address ([UInt32]$item.address) -Label $item.label -Group "known_forcanitro_registers"
        }

        foreach ($address in 0xA0..0xAF) {
            $ecReads += Invoke-EcProbeRead -ProbePath $resolvedEcProbePath -Address ([UInt32]$address) -Label "temperature candidate byte" -Group "temperature_candidate_range_A0_AF"
        }

        $report.embeddedController.reads = $ecReads
    }
}

$report.nvidiaSmi = Get-NvidiaSmiSnapshot

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory -and -not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ""
Write-Host "ForcaNitro read-only compatibility diagnostic complete." -ForegroundColor Green
Write-Host "Report: $OutputPath"
Write-Host "No EC writes were executed. No Acer WMI Set* methods were called. No data was uploaded."
Write-Host ""
