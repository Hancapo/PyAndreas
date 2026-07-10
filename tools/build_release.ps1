param(
    [Parameter(Mandatory = $true)]
    [string]$PluginSdkDir,
    [Parameter(Mandatory = $true)]
    [string]$PythonX86Dir,
    [string]$RuntimeDir,
    [string]$GameDir
)

$ErrorActionPreference = "Stop"
$project = Resolve-Path "$PSScriptRoot\..\plugin\PyAndreas.vcxproj"
$msbuild = Get-Command msbuild -ErrorAction SilentlyContinue
if (-not $msbuild) {
    $candidate = @(
        Get-ChildItem "C:\Program Files\Microsoft Visual Studio" `
            -Filter MSBuild.exe -Recurse -ErrorAction SilentlyContinue
        Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" `
            -Filter MSBuild.exe -Recurse -ErrorAction SilentlyContinue
    ) | Select-Object -First 1
    if (-not $candidate) {
        throw "MSBuild.exe was not found"
    }
    $msbuild = $candidate.FullName
} else {
    $msbuild = $msbuild.Source
}

& $msbuild $project /m /p:"Configuration=Release GTA-SA" /p:Platform=Win32 `
    /p:PLUGIN_SDK_DIR="$PluginSdkDir" /p:PYTHON_X86_DIR="$PythonX86Dir"
if ($LASTEXITCODE -ne 0) {
    throw "Native build failed with exit code $LASTEXITCODE"
}

if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $PSScriptRoot "..\dist\PyAndreas\python"
}
$args = @("$PSScriptRoot\package_release.py", "--runtime", $RuntimeDir)
if ($GameDir) {
    $args += @("--game-dir", $GameDir)
}
& python @args
if ($LASTEXITCODE -ne 0) {
    throw "Release packaging failed with exit code $LASTEXITCODE"
}
