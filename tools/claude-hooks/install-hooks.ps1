# Installs the tracked Claude Code hooks into this repo's local .claude/ directory.
# Windows PowerShell 5.1 compatible. Source of truth: tools/claude-hooks/hooks/.
# The installed .claude/ state is generated and gitignored - never edit it directly;
# edit the tracked sources here and re-run this script.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\claude-hooks\install-hooks.ps1
#   ... -Force   overwrite a diverged .claude/settings.json (a timestamped .bak is kept)

[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$srcHooks = Join-Path $PSScriptRoot 'hooks'
$dstHooks = Join-Path $repoRoot '.claude\hooks'
$templatePath = Join-Path $srcHooks 'settings.template.json'
$settingsPath = Join-Path $repoRoot '.claude\settings.json'

if (-not (Test-Path $templatePath)) {
    throw "Template not found: $templatePath - run from a full checkout."
}

New-Item -ItemType Directory -Force -Path $dstHooks | Out-Null

$copied = @()
foreach ($file in Get-ChildItem -Path $srcHooks -Filter '*.py') {
    Copy-Item -Path $file.FullName -Destination (Join-Path $dstHooks $file.Name) -Force
    $copied += $file.Name
}
Write-Output ("Installed hook scripts -> .claude\hooks\ : " + ($copied -join ', '))

# Normalize both sides through the JSON parser so formatting/line-ending
# differences don't count as divergence.
$templateJson = (Get-Content $templatePath -Raw | ConvertFrom-Json) | ConvertTo-Json -Depth 10

if (Test-Path $settingsPath) {
    $existingJson = $null
    try {
        $existingJson = (Get-Content $settingsPath -Raw | ConvertFrom-Json) | ConvertTo-Json -Depth 10
    } catch {
        Write-Warning ".claude\settings.json exists but is not valid JSON."
    }
    if ($existingJson -eq $templateJson) {
        Write-Output '.claude\settings.json already matches the template - no change.'
    } elseif ($Force) {
        $bak = $settingsPath + '.bak-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Copy-Item -Path $settingsPath -Destination $bak
        [System.IO.File]::WriteAllText($settingsPath, (Get-Content $templatePath -Raw), (New-Object System.Text.UTF8Encoding($false)))
        Write-Output (".claude\settings.json overwritten (backup: " + (Split-Path -Leaf $bak) + ")")
    } else {
        Write-Warning '.claude\settings.json differs from the template. It may contain local customizations.'
        Write-Warning 'Merge the "hooks" block from tools\claude-hooks\hooks\settings.template.json manually,'
        Write-Warning 'or re-run with -Force to overwrite (a timestamped backup will be kept).'
        exit 1
    }
} else {
    [System.IO.File]::WriteAllText($settingsPath, (Get-Content $templatePath -Raw), (New-Object System.Text.UTF8Encoding($false)))
    Write-Output 'Created .claude\settings.json from template.'
}

Write-Output 'Done. Run tools\claude-hooks\verify-hooks.ps1 to confirm the installation.'
