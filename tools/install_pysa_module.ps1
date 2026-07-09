[CmdletBinding()]
param(
    [string]$Python,
    [switch]$User
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-SelectedPython {
    param([string[]]$Arguments)

    if ($Python) {
        & $Python @Arguments
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
    } else {
        & python @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

$pipArgs = @("-m", "pip", "install")
if ($User) {
    $pipArgs += "--user"
}
$pipArgs += @("-e", $RepoRoot.Path)

Write-Host "Installing PyAndreas as an editable Python package..."
Invoke-SelectedPython $pipArgs

Write-Host ""
Write-Host "Verifying import..."
Invoke-SelectedPython @(
    "-c",
    "import pysa; print('pysa', pysa.__version__, 'from', pysa.__file__); print('player OOP:', hasattr(pysa.player, 'weapons'), hasattr(pysa.player, 'wanted'))"
)

Write-Host ""
Write-Host "Done. Restart your editor or reload the Python language server if autocomplete was already open."
