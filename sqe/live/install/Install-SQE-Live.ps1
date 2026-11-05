[CmdletBinding()]
param(
    [string]$DcsPath,
    [string]$SavedGamesPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$bundle = $PSScriptRoot
$utf8 = New-Object System.Text.UTF8Encoding($false)

if (Get-Process -Name DCS,DCS_updater -ErrorAction SilentlyContinue) {
    throw 'Close DCS and its updater before installing.'
}
if (-not $DcsPath) {
    $candidates = @()
    foreach ($key in @('HKCU:\SOFTWARE\Eagle Dynamics\DCS World', 'HKCU:\SOFTWARE\Eagle Dynamics\DCS World OpenBeta')) {
        $reg = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
        if ($reg -and $reg.PSObject.Properties['Path']) { $candidates += $reg.Path }
    }
    $candidates += @('C:\Program Files\Eagle Dynamics\DCS World', 'C:\Program Files\Eagle Dynamics\DCS World OpenBeta',
        'C:\Program Files (x86)\Steam\steamapps\common\DCSWorld')
    $found = @($candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'Scripts\MissionScripting.lua') } | Select-Object -Unique)
    if ($found.Count -eq 1) { $DcsPath = $found[0] }
    else { $DcsPath = Read-Host 'Full DCS installation folder (contains bin and Scripts)' }
}
if (-not $SavedGamesPath) {
    $savedRoot = Join-Path $env:USERPROFILE 'Saved Games'
    $folders = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -ErrorAction SilentlyContinue
    $savedKey = '{4C5C32FF-BB9D-43B0-BF21-3020BC4AB90E}'
    if ($folders -and $folders.PSObject.Properties[$savedKey]) {
        $savedRoot = [Environment]::ExpandEnvironmentVariables($folders.$savedKey)
    }
    $found = @('DCS','DCS.openbeta' | ForEach-Object { Join-Path $savedRoot $_ } | Where-Object { Test-Path -LiteralPath $_ })
    if ($found.Count -eq 1) { $SavedGamesPath = $found[0] }
    elseif ($found.Count -eq 0) { $SavedGamesPath = Join-Path $savedRoot 'DCS' }
    else { $SavedGamesPath = Read-Host 'Full Saved Games DCS profile folder to use' }
}
$DcsPath = [IO.Path]::GetFullPath($DcsPath.Trim('"'))
$SavedGamesPath = [IO.Path]::GetFullPath($SavedGamesPath.Trim('"'))
$missionScript = Join-Path $DcsPath 'Scripts\MissionScripting.lua'
if (-not (Test-Path -LiteralPath $missionScript)) { throw "Cannot find $missionScript" }
if ($DcsPath -eq $SavedGamesPath) { throw 'Installation and Saved Games folders must be different.' }

# Verify the distributed files before touching the installation.
$manifest = Get-Content -LiteralPath (Join-Path $bundle 'SHA256SUMS.json') -Raw | ConvertFrom-Json
foreach ($item in $manifest.PSObject.Properties) {
    $path = Join-Path $bundle $item.Name
    if (-not (Test-Path -LiteralPath $path)) { throw "Package file missing: $($item.Name)" }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Value) {
        throw "Package file changed or damaged: $($item.Name)"
    }
}
$original = [IO.File]::ReadAllText($missionScript)
$begin = '-- SQE-LIVE BRIDGE BEGIN'
$end = '-- SQE-LIVE BRIDGE END'
$blockPattern = '(?ms)^-- SQE-LIVE BRIDGE BEGIN\r?\n.*?^-- SQE-LIVE BRIDGE END\r?\n?'
$clean = [regex]::Replace($original, $blockPattern, '')
if ($clean.Contains($begin) -or $clean.Contains($end)) { throw 'Incomplete SQE bridge marker found. Restore the file backup before retrying.' }
$anchor = [regex]::Match($clean, '(?m)^[ \t]*local function sanitizeModule\s*\(')
if (-not $anchor.Success) { throw 'Unsupported MissionScripting.lua layout: sanitization entry not found. No files were changed.' }
$newline = if ($original.Contains("`r`n")) { "`r`n" } else { "`n" }
$block = @'
-- SQE-LIVE BRIDGE BEGIN
do
    local path = lfs.writedir() .. "Scripts/SQE-Live/storage_boot.lua"
    local ok, err = pcall(dofile, path)
    if not ok and log and log.write then log.write("SQE-Live", log.ERROR, tostring(err)) end
end
-- SQE-LIVE BRIDGE END
'@ -replace "`r?`n", $newline
$updated = $clean.Insert($anchor.Index, $block.TrimEnd() + $newline)

$scriptsDir = Join-Path $SavedGamesPath 'Scripts\SQE-Live'
$hooksDir = Join-Path $SavedGamesPath 'Scripts\Hooks'
$missionsDir = Join-Path $SavedGamesPath 'Missions\SQE-Live'
foreach ($dir in @($scriptsDir,$hooksDir,$missionsDir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
Copy-Item -Path (Join-Path $bundle 'Scripts\SQE-Live\*') -Destination $scriptsDir -Force
Copy-Item -LiteralPath (Join-Path $bundle 'Scripts\Hooks\SQE-Live.lua') -Destination $hooksDir -Force
Copy-Item -LiteralPath (Join-Path $bundle 'Missions\SQE_Live_Syria.miz') -Destination $missionsDir -Force
$legacyMission = Join-Path $bundle 'Missions\SQE_Live_Syria_Legacy.miz'
if (Test-Path -LiteralPath $legacyMission) { Copy-Item -LiteralPath $legacyMission -Destination $missionsDir -Force }

# Keep a uniquely named copy and preserve all unrelated changes. The uninstall
# removes our marked block; it does not restore an old whole-file backup.
$backup = $missionScript + '.sqe-live-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss-ffff') + '.bak'
if ($updated -ne $original) {
    $temporary = $missionScript + '.sqe-live.tmp'
    try {
        [IO.File]::WriteAllText($temporary, $updated, $utf8)
        [IO.File]::Replace($temporary, $missionScript, $backup)
    } catch {
        Remove-Item -LiteralPath $temporary -ErrorAction SilentlyContinue
        throw "Could not patch MissionScripting.lua. Existing file retained. If DCS is under Program Files, rerun PowerShell as administrator with the SAME -SavedGamesPath. $($_.Exception.Message)"
    }
}
$recordDir = Join-Path $SavedGamesPath 'SQE-Live'
New-Item -ItemType Directory -Path $recordDir -Force | Out-Null
$version = ((Get-Content -LiteralPath (Join-Path $bundle 'VERSION.txt') -TotalCount 1) -replace '^SQE Live ', '')
@{ installed_at=[DateTime]::Now.ToString('o'); dcs_path=$DcsPath; saved_games=$SavedGamesPath; version=$version } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $recordDir 'installation.json') -Encoding UTF8
Write-Host ''
Write-Host 'SQE Live installed.' -ForegroundColor Green
Write-Host "Mission: $(Join-Path $missionsDir 'SQE_Live_Syria.miz')"
Write-Host 'In DCS: Missions > SQE-Live > SQE_Live_Syria. Ctrl+Shift+Q opens Operations.'
Write-Host 'Check that SAVE reports success. DCS updates/repairs may require rerunning this installer.'
Write-Host 'Campaign saves are preserved when reinstalling or uninstalling.'
