[CmdletBinding()]
param(
    [string]$SavedGamesPath,
    [string]$OutputPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $SavedGamesPath) {
    $savedRoot = Join-Path $env:USERPROFILE 'Saved Games'
    $folders = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -ErrorAction SilentlyContinue
    $savedKey = '{4C5C32FF-BB9D-43B0-BF21-3020BC4AB90E}'
    if ($folders -and $folders.PSObject.Properties[$savedKey]) {
        $savedRoot = [Environment]::ExpandEnvironmentVariables($folders.$savedKey)
    }
    $found = @('DCS','DCS.openbeta' | ForEach-Object { Join-Path $savedRoot $_ } | Where-Object { Test-Path -LiteralPath $_ })
    if ($found.Count -eq 1) { $SavedGamesPath = $found[0] }
    else { $SavedGamesPath = Read-Host 'Full Saved Games DCS profile folder to collect' }
}
$SavedGamesPath = [IO.Path]::GetFullPath($SavedGamesPath.Trim('"'))
if (-not (Test-Path -LiteralPath $SavedGamesPath -PathType Container)) { throw 'DCS profile folder not found.' }
$root = Join-Path $SavedGamesPath 'SQE-Live'
$tag = [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
if (-not $OutputPath) { $OutputPath = Join-Path $SavedGamesPath "SQE-Live-Diagnostics-$tag.zip" }
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $OutputPath) { throw 'Output already exists; choose a new ZIP filename.' }
if ([IO.Path]::GetExtension($OutputPath) -ne '.zip') { throw 'Output must be a .zip file.' }

# This unique directory belongs only to this invocation. Never scan/copy the profile recursively.
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('SQE-Live-collect-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary | Out-Null
try {
    $notes = @('SQE Live local diagnostic collection',
        'Checks describe observed APIs/data only; actual rendering and flight behavior remain unverified.',
        'No network upload, campaign saves, full DCS log, or unrelated profile files are included.',
        'Reports and log excerpts may contain local paths. Review before sharing.', '')
    foreach ($name in @('diagnostics-runtime.json','diagnostics-ui.json','installation.json')) {
        $source = Join-Path $root $name
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            if ((Get-Item -LiteralPath $source).Length -le 128KB) {
                Copy-Item -LiteralPath $source -Destination (Join-Path $temporary $name)
                $notes += "Included: $name"
            } else { $notes += "Skipped oversized file: $name" }
        } else { $notes += "Not yet present: $name" }
    }
    $logPath = Join-Path $SavedGamesPath 'Logs\dcs.log'
    if (Test-Path -LiteralPath $logPath -PathType Leaf) {
        $lines = @(Get-Content -LiteralPath $logPath -Tail 2000 |
            Where-Object { $_ -match '(?i)SQE[ -]Live' } | Select-Object -Last 200 |
            ForEach-Object { if ($_.Length -gt 1000) { $_.Substring(0,1000) } else { $_ } })
        [IO.File]::WriteAllLines((Join-Path $temporary 'sqe-log-excerpt.txt'), [string[]]$lines)
        $notes += 'Included: up to 200 SQE Live entries from the last 2000 log lines.'
    } else { $notes += 'DCS log not present.' }
    [IO.File]::WriteAllLines((Join-Path $temporary 'README.txt'), [string[]]$notes)
    Compress-Archive -Path (Join-Path $temporary '*') -DestinationPath $OutputPath
    Write-Host "Local report created: $OutputPath"
    Write-Host 'Nothing was sent. Campaign saves were not changed.'
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force
}
