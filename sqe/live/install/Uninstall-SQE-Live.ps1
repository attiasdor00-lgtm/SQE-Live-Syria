[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SavedGamesPath,
    [string]$DcsPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (Get-Process -Name DCS,DCS_updater -ErrorAction SilentlyContinue) { throw 'Close DCS and its updater first.' }
$SavedGamesPath = [IO.Path]::GetFullPath($SavedGamesPath.Trim('"'))
if (-not $DcsPath) {
    $record = Join-Path $SavedGamesPath 'SQE-Live\installation.json'
    if (Test-Path -LiteralPath $record) { $DcsPath = (Get-Content -LiteralPath $record -Raw | ConvertFrom-Json).dcs_path }
}
if (-not $DcsPath) { throw 'Supply -DcsPath to remove the marked bridge from MissionScripting.lua.' }
$script = Join-Path $DcsPath 'Scripts\MissionScripting.lua'
if (Test-Path -LiteralPath $script) {
    $original = [IO.File]::ReadAllText($script)
    $updated = [regex]::Replace($original, '(?ms)^-- SQE-LIVE BRIDGE BEGIN\r?\n.*?^-- SQE-LIVE BRIDGE END\r?\n?', '')
    if ($updated.Contains('-- SQE-LIVE BRIDGE')) { throw 'Incomplete bridge marker. Restore your file backup manually.' }
    if ($updated -ne $original) {
        $backup = $script + '.sqe-uninstall-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss-ffff') + '.bak'
        $temporary = $script + '.sqe-live.tmp'
        [IO.File]::WriteAllText($temporary, $updated, (New-Object System.Text.UTF8Encoding($false)))
        [IO.File]::Replace($temporary, $script, $backup)
    }
}
# Exact package files only. Never delete a profile, campaign save, or other hook.
foreach ($name in @('json.lua','storage.lua','storage_boot.lua','view.lua','map.lua','map_ui.lua','Operations.dlg')) {
    $path = Join-Path $SavedGamesPath "Scripts\SQE-Live\$name"
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
}
foreach ($relative in @('Scripts\Hooks\SQE-Live.lua','Missions\SQE-Live\SQE_Live_Syria.miz')) {
    $path = Join-Path $SavedGamesPath $relative
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
}
Write-Host 'SQE Live removed. Campaign saves and backups were retained.'
