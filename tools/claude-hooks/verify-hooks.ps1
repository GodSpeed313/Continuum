# Verifies the installed Claude Code hooks match the tracked sources and actually work.
# Windows PowerShell 5.1 compatible.
#
# Checks:
#   1. python is on PATH
#   2. every tracked hook script is installed byte-identical (SHA256)
#   3. .claude/settings.json matches the template (JSON-normalized compare)
#   4. functional smoke tests: guard blocks a force-push (exit 2) and passes a
#      benign command (exit 0); post-edit hook no-ops on an out-of-scope file
#   5. with -Full: the Stop hook runs the real full suite (slow; requires deps)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\claude-hooks\verify-hooks.ps1 [-Full]

[CmdletBinding()]
param([switch]$Full)

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$srcHooks = Join-Path $PSScriptRoot 'hooks'
$dstHooks = Join-Path $repoRoot '.claude\hooks'
$settingsPath = Join-Path $repoRoot '.claude\settings.json'
$templatePath = Join-Path $srcHooks 'settings.template.json'

$failures = 0
function Report([bool]$ok, [string]$label) {
    if ($ok) { Write-Output ("  PASS  " + $label) }
    else { Write-Output ("  FAIL  " + $label); $script:failures++ }
}

Write-Output '== Claude hooks verification =='

# 1. python available
$py = $null
try { $py = Get-Command python -ErrorAction Stop } catch {}
Report ($null -ne $py) 'python on PATH'
if ($null -eq $py) { Write-Output 'Cannot continue without python.'; exit 1 }

# 2. installed scripts match tracked sources
foreach ($file in Get-ChildItem -Path $srcHooks -Filter '*.py') {
    $installed = Join-Path $dstHooks $file.Name
    if (Test-Path $installed) {
        $a = (Get-FileHash -Algorithm SHA256 $file.FullName).Hash
        $b = (Get-FileHash -Algorithm SHA256 $installed).Hash
        Report ($a -eq $b) ($file.Name + ' installed and byte-identical to tracked source')
    } else {
        Report $false ($file.Name + ' installed (missing - run install-hooks.ps1)')
    }
}

# 3. settings.json matches template
if (Test-Path $settingsPath) {
    $ok = $false
    try {
        $a = (Get-Content $templatePath -Raw | ConvertFrom-Json) | ConvertTo-Json -Depth 10
        $b = (Get-Content $settingsPath -Raw | ConvertFrom-Json) | ConvertTo-Json -Depth 10
        $ok = ($a -eq $b)
    } catch {}
    Report $ok '.claude\settings.json matches template'
} else {
    Report $false '.claude\settings.json exists (missing - run install-hooks.ps1)'
}

# 4. functional smoke tests (run against the INSTALLED copies, from repo root)
Push-Location $repoRoot
try {
    '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | python .claude/hooks/pre_bash_guard.py
    Report ($LASTEXITCODE -eq 2) 'pre_bash_guard blocks git push --force (exit 2)'

    '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | python .claude/hooks/pre_bash_guard.py
    Report ($LASTEXITCODE -eq 0) 'pre_bash_guard passes benign command (exit 0)'

    $probe = '{"cwd":"' + ($repoRoot -replace '\\', '\\\\') + '","tool_input":{"file_path":"' + ($repoRoot -replace '\\', '\\\\') + '\\\\README.md"}}'
    $probe | python .claude/hooks/post_edit_tests.py
    Report ($LASTEXITCODE -eq 0) 'post_edit_tests no-ops on out-of-scope file (exit 0)'

    if ($Full) {
        Write-Output '  ....  Stop hook full-suite run (slow):'
        '{"cwd":"' + ($repoRoot -replace '\\', '\\\\') + '"}' | python .claude/hooks/stop_suite_notify.py
        Report ($LASTEXITCODE -eq 0) 'stop_suite_notify completed (exit 0; suite result printed above)'
    } else {
        Write-Output '  SKIP  stop_suite_notify full-suite run (use -Full)'
    }
} finally {
    Pop-Location
}

Write-Output ''
if ($failures -eq 0) {
    Write-Output 'All checks passed.'
    exit 0
} else {
    Write-Output ("{0} check(s) FAILED." -f $failures)
    exit 1
}
