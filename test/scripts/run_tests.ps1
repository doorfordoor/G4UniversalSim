param(
    [string]$Executable = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

if ([string]::IsNullOrWhiteSpace($Executable)) {
    $candidates = @(
        Join-Path $Root "build\Release\G4UniversalSim.exe"
        Join-Path $Root "build\Debug\G4UniversalSim.exe"
        Join-Path $Root "build\G4UniversalSim.exe"
        Join-Path $Root "build_vs\Release\G4UniversalSim.exe"
        Join-Path $Root "build_vs\Debug\G4UniversalSim.exe"
    )
    $Executable = ($candidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

if ([string]::IsNullOrWhiteSpace($Executable) -or -not (Test-Path $Executable)) {
    throw "G4UniversalSim executable not found. Pass -Executable path\to\G4UniversalSim.exe"
}

$runs = @(
    @{ Name = "layered_device"; Config = "test\main_layered_device.ini"; Macro = "test\macros\test_layered_device_full.mac"; Output = "test\output\layered_device" },
    @{ Name = "hierarchical"; Config = "test\main_hierarchical.ini"; Macro = "test\macros\test_hierarchical_full.mac"; Output = "test\output\hierarchical" }
)

Push-Location $Root
try {
    foreach ($run in $runs) {
        New-Item -ItemType Directory -Force $run.Output | Out-Null
        $log = Join-Path $run.Output "run.log"
        Write-Host "Running $($run.Name)..."
        & $Executable --config $run.Config --macro $run.Macro --output $run.Output --run-name "test_$($run.Name)" 2>&1 | Tee-Object -FilePath $log
        if ($LASTEXITCODE -ne 0) {
            throw "$($run.Name) failed with exit code $LASTEXITCODE. See $log"
        }
    }
} finally {
    Pop-Location
}
