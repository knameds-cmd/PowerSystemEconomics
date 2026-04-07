[CmdletBinding()]
param(
    [string[]]$Source = @(
        "smp_forecast_demand",
        "regional_renewables",
        "power_market_gen_info",
        "fuel_cost",
        "smp_decision_by_fuel"
    ),
    [ValidatePattern('^\d{8}$')]
    [string]$DateFrom = (Get-Date).ToString("yyyyMMdd"),
    [ValidatePattern('^\d{8}$')]
    [string]$DateTo = (Get-Date).ToString("yyyyMMdd"),
    [ValidatePattern('^\d{6}$')]
    [string]$MonthFrom = (Get-Date).ToString("yyyyMM"),
    [ValidatePattern('^\d{6}$')]
    [string]$MonthTo = (Get-Date).ToString("yyyyMM"),
    [int]$PageSize = 500,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-RepoRoot {
    if ($PSScriptRoot) {
        return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    }
    return (Get-Location).Path
}

function Load-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            return
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Convert-TomlValue {
    param([string]$RawValue)

    $value = $RawValue.Trim()
    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
        return $value.Substring(1, $value.Length - 2)
    }

    if ($value -match '^\[(.*)\]$') {
        $inner = $Matches[1].Trim()
        if (-not $inner) {
            return @()
        }

        return @(
            $inner.Split(",") | ForEach-Object {
                $item = $_.Trim()
                if ($item.StartsWith('"') -and $item.EndsWith('"')) {
                    $item.Substring(1, $item.Length - 2)
                }
                else {
                    $item
                }
            }
        )
    }

    if ($value -match '^(true|false)$') {
        return [System.Convert]::ToBoolean($value)
    }

    if ($value -match '^-?\d+$') {
        return [int]$value
    }

    return $value
}

function Read-SimpleToml {
    param([string]$Path)

    $result = @{}
    $current = $result

    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }

        if ($line -match '^\[(.+)\]$') {
            $sectionPath = $Matches[1].Split(".")
            $current = $result
            foreach ($segment in $sectionPath) {
                if (-not $current.ContainsKey($segment)) {
                    $current[$segment] = @{}
                }
                $current = $current[$segment]
            }
            continue
        }

        $parts = $line -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = Convert-TomlValue -RawValue $parts[1]
        $current[$key] = $value
    }

    return $result
}

function Get-RequiredEnvValue {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }

    return $value
}

function New-Directory {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-DateRange {
    param(
        [string]$Start,
        [string]$End
    )

    $current = [datetime]::ParseExact($Start, "yyyyMMdd", $null)
    $last = [datetime]::ParseExact($End, "yyyyMMdd", $null)
    while ($current -le $last) {
        $current.ToString("yyyyMMdd")
        $current = $current.AddDays(1)
    }
}

function Get-MonthRange {
    param(
        [string]$Start,
        [string]$End
    )

    $current = [datetime]::ParseExact($Start + "01", "yyyyMMdd", $null)
    $last = [datetime]::ParseExact($End + "01", "yyyyMMdd", $null)
    while ($current -le $last) {
        $current.ToString("yyyyMM")
        $current = $current.AddMonths(1)
    }
}

function New-UriWithQuery {
    param(
        [string]$BaseUrl,
        [hashtable]$Query
    )

    $builder = [System.UriBuilder]::new($BaseUrl)
    $pairs = foreach ($key in $Query.Keys) {
        $encodedKey = [System.Uri]::EscapeDataString([string]$key)
        $encodedValue = [System.Uri]::EscapeDataString([string]$Query[$key])
        "$encodedKey=$encodedValue"
    }
    $builder.Query = ($pairs -join "&")
    return $builder.Uri.AbsoluteUri
}

function Get-SafeLogUri {
    param([string]$Uri)

    return ($Uri -replace '(serviceKey=)[^&]+', '${1}***')
}

function Save-JsonFile {
    param(
        [string]$Path,
        $Object
    )

    $Object | ConvertTo-Json -Depth 100 | Set-Content -Path $Path -Encoding UTF8
}

function Invoke-JsonGet {
    param(
        [string]$BaseUrl,
        [hashtable]$Query,
        [hashtable]$Headers = @{}
    )

    $uri = New-UriWithQuery -BaseUrl $BaseUrl -Query $Query
    Write-Host ("GET " + (Get-SafeLogUri -Uri $uri))
    if ($DryRun) {
        return @{
            __dryRun = $true
            uri = (Get-SafeLogUri -Uri $uri)
            headers = $Headers
        }
    }

    return Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers
}

function Get-DataGoItems {
    param($Response)

    if ($null -eq $Response.body) {
        return @()
    }

    if ($null -eq $Response.body.items) {
        return @()
    }

    $items = $Response.body.items.item
    if ($null -eq $items) {
        return @()
    }

    if ($items -is [System.Array]) {
        return $items
    }

    return @($items)
}

function Save-Manifest {
    param(
        [string]$Directory,
        [hashtable]$Manifest
    )

    Save-JsonFile -Path (Join-Path $Directory "manifest.json") -Object $Manifest
}

function Invoke-DataGoPagedDownload {
    param(
        [string]$SourceKey,
        [hashtable]$SourceConfig,
        [hashtable]$ExtraQuery,
        [string]$OutputDirectory,
        [string]$ServiceKey
    )

    New-Directory -Path $OutputDirectory

    $page = 1
    $allPageFiles = @()
    $totalCount = $null

    do {
        $query = @{
            serviceKey = $ServiceKey
            pageNo = $page
            numOfRows = $PageSize
            dataType = "json"
        }

        foreach ($key in $ExtraQuery.Keys) {
            $query[$key] = $ExtraQuery[$key]
        }

        $response = Invoke-JsonGet -BaseUrl ("$($SourceConfig.base_url)/$($SourceConfig.operation)") -Query $query
        $pageFile = Join-Path $OutputDirectory ("page-{0:D4}.json" -f $page)

        if ($DryRun) {
            Save-JsonFile -Path $pageFile -Object $response
            $allPageFiles += (Split-Path $pageFile -Leaf)
            break
        }

        Save-JsonFile -Path $pageFile -Object $response
        $allPageFiles += (Split-Path $pageFile -Leaf)

        if ($null -eq $totalCount) {
            $totalCount = [int]$response.body.totalCount
        }

        $items = Get-DataGoItems -Response $response
        if ($items.Count -lt $PageSize) {
            break
        }

        $page += 1
    } while ($true)

    $manifest = @{
        source = $SourceKey
        provider = $SourceConfig.provider
        base_url = $SourceConfig.base_url
        operation = $SourceConfig.operation
        query = $ExtraQuery
        downloaded_at = (Get-Date).ToString("s")
        page_size = $PageSize
        pages = $allPageFiles
        dry_run = [bool]$DryRun
        total_count = $totalCount
    }
    Save-Manifest -Directory $OutputDirectory -Manifest $manifest
}

function Get-LatestRenewableSwaggerPath {
    param([hashtable]$SourceConfig)

    if ($SourceConfig.ContainsKey("latest_path") -and $SourceConfig.latest_path) {
        return [pscustomobject]@{
            path = [string]$SourceConfig.latest_path
            summary = "Configured latest renewable dataset path"
            versionDate = [string]$SourceConfig.latest_version
        }
    }

    $swagger = Invoke-RestMethod -Method Get -Uri $SourceConfig.swagger_url
    $candidatePaths = @()

    foreach ($path in $swagger.paths.PSObject.Properties) {
        $getOperation = $path.Value.get
        if ($null -eq $getOperation) {
            continue
        }

        $summary = [string]$getOperation.summary
        if ($summary -notmatch "태양광 및 풍력") {
            continue
        }

        $versionDate = ""
        if ($summary -match "(\d{8})") {
            $versionDate = $Matches[1]
        }

        $candidatePaths += [pscustomobject]@{
            path = $path.Name
            summary = $summary
            versionDate = $versionDate
        }
    }

    if (-not $candidatePaths) {
        throw "Could not find a renewable path in the odcloud swagger document."
    }

    return $candidatePaths |
        Sort-Object versionDate -Descending |
        Select-Object -First 1
}

function Invoke-OdcloudPagedDownload {
    param(
        [string]$SourceKey,
        [hashtable]$SourceConfig,
        [string]$OutputDirectory,
        [string]$ServiceKey
    )

    $pathInfo = Get-LatestRenewableSwaggerPath -SourceConfig $SourceConfig
    New-Directory -Path $OutputDirectory

    $baseUrl = "https://api.odcloud.kr/api$($pathInfo.path)"
    $page = 1
    $allPageFiles = @()
    $totalCount = $null

    do {
        $query = @{
            page = $page
            perPage = $PageSize
            returnType = "JSON"
            serviceKey = $ServiceKey
        }

        $response = Invoke-JsonGet -BaseUrl $baseUrl -Query $query
        $pageFile = Join-Path $OutputDirectory ("page-{0:D4}.json" -f $page)

        if ($DryRun) {
            Save-JsonFile -Path $pageFile -Object $response
            $allPageFiles += (Split-Path $pageFile -Leaf)
            break
        }

        Save-JsonFile -Path $pageFile -Object $response
        $allPageFiles += (Split-Path $pageFile -Leaf)

        if ($null -eq $totalCount) {
            $totalCount = [int]$response.totalCount
        }

        $currentCount = 0
        if ($null -ne $response.currentCount) {
            $currentCount = [int]$response.currentCount
        }
        elseif ($null -ne $response.data) {
            $currentCount = @($response.data).Count
        }

        if ($currentCount -lt $PageSize) {
            break
        }

        $page += 1
    } while ($true)

    $manifest = @{
        source = $SourceKey
        provider = $SourceConfig.provider
        base_url = $baseUrl
        swagger_url = $SourceConfig.swagger_url
        selected_path = $pathInfo.path
        selected_summary = $pathInfo.summary
        downloaded_at = (Get-Date).ToString("s")
        page_size = $PageSize
        pages = $allPageFiles
        dry_run = [bool]$DryRun
        total_count = $totalCount
    }
    Save-Manifest -Directory $OutputDirectory -Manifest $manifest
}

function Invoke-SourceDownload {
    param(
        [string]$SourceKey,
        [hashtable]$Config,
        [string]$RepoRoot
    )

    $sourceConfig = $Config.sources[$SourceKey]
    if ($null -eq $sourceConfig) {
        throw "Unknown source key: $SourceKey"
    }

    switch ($SourceKey) {
        "smp_forecast_demand" {
            $dataGoKey = ""
            if (-not $DryRun) {
                $dataGoKey = Get-RequiredEnvValue -Name $Config.auth.data_go_kr_service_key_env
            }
            foreach ($day in Get-DateRange -Start $DateFrom -End $DateTo) {
                $outputDirectory = Join-Path $RepoRoot (Join-Path $sourceConfig.target_path ("date=$day"))
                Invoke-DataGoPagedDownload -SourceKey $SourceKey -SourceConfig $sourceConfig -ExtraQuery @{ date = $day } -OutputDirectory $outputDirectory -ServiceKey $dataGoKey
            }
        }
        "smp_decision_by_fuel" {
            $dataGoKey = ""
            if (-not $DryRun) {
                $dataGoKey = Get-RequiredEnvValue -Name $Config.auth.data_go_kr_service_key_env
            }
            foreach ($day in Get-DateRange -Start $DateFrom -End $DateTo) {
                $outputDirectory = Join-Path $RepoRoot (Join-Path $sourceConfig.target_path ("date=$day"))
                Invoke-DataGoPagedDownload -SourceKey $SourceKey -SourceConfig $sourceConfig -ExtraQuery @{ tradeDay = $day } -OutputDirectory $outputDirectory -ServiceKey $dataGoKey
            }
        }
        "fuel_cost" {
            $dataGoKey = ""
            if (-not $DryRun) {
                $dataGoKey = Get-RequiredEnvValue -Name $Config.auth.data_go_kr_service_key_env
            }
            foreach ($month in Get-MonthRange -Start $MonthFrom -End $MonthTo) {
                $outputDirectory = Join-Path $RepoRoot (Join-Path $sourceConfig.target_path ("month=$month"))
                Invoke-DataGoPagedDownload -SourceKey $SourceKey -SourceConfig $sourceConfig -ExtraQuery @{ day = $month } -OutputDirectory $outputDirectory -ServiceKey $dataGoKey
            }
        }
        "power_market_gen_info" {
            $dataGoKey = ""
            if (-not $DryRun) {
                $dataGoKey = Get-RequiredEnvValue -Name $Config.auth.data_go_kr_service_key_env
            }
            $stamp = (Get-Date).ToString("yyyyMMddTHHmmss")
            $outputDirectory = Join-Path $RepoRoot (Join-Path $sourceConfig.target_path ("snapshot=$stamp"))
            Invoke-DataGoPagedDownload -SourceKey $SourceKey -SourceConfig $sourceConfig -ExtraQuery @{} -OutputDirectory $outputDirectory -ServiceKey $dataGoKey
        }
        "regional_renewables" {
            $odcloudKey = ""
            if (-not $DryRun) {
                $odcloudKey = Get-RequiredEnvValue -Name $Config.auth.odcloud_service_key_env
            }
            $stamp = (Get-Date).ToString("yyyyMMddTHHmmss")
            $outputDirectory = Join-Path $RepoRoot (Join-Path $sourceConfig.target_path ("snapshot=$stamp"))
            Invoke-OdcloudPagedDownload -SourceKey $SourceKey -SourceConfig $sourceConfig -OutputDirectory $outputDirectory -ServiceKey $odcloudKey
        }
        "kpx_member_status" {
            Write-Warning "kpx_member_status is a manual web reference and is not downloaded by this script."
        }
        default {
            throw "Source is not supported by the downloader: $SourceKey"
        }
    }
}

$repoRoot = Get-RepoRoot
Load-DotEnv -Path (Join-Path $repoRoot ".env")

$configPath = Join-Path $repoRoot "config/data_sources.template.toml"
if (-not (Test-Path $configPath)) {
    throw "Missing config file: $configPath"
}

$config = Read-SimpleToml -Path $configPath

foreach ($sourceKey in $Source) {
    Invoke-SourceDownload -SourceKey $sourceKey -Config $config -RepoRoot $repoRoot
}
