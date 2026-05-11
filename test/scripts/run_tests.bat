@echo off
setlocal

set "ROOT=%~dp0..\.."
set "EXE=%~1"

if "%EXE%"=="" if exist "%ROOT%\build\Release\G4UniversalSim.exe" set "EXE=%ROOT%\build\Release\G4UniversalSim.exe"
if "%EXE%"=="" if exist "%ROOT%\build\Debug\G4UniversalSim.exe" set "EXE=%ROOT%\build\Debug\G4UniversalSim.exe"
if "%EXE%"=="" if exist "%ROOT%\build\G4UniversalSim.exe" set "EXE=%ROOT%\build\G4UniversalSim.exe"
if "%EXE%"=="" if exist "%ROOT%\build_vs\Release\G4UniversalSim.exe" set "EXE=%ROOT%\build_vs\Release\G4UniversalSim.exe"
if "%EXE%"=="" if exist "%ROOT%\build_vs\Debug\G4UniversalSim.exe" set "EXE=%ROOT%\build_vs\Debug\G4UniversalSim.exe"

if "%EXE%"=="" (
  echo G4UniversalSim executable not found. Pass it as the first argument.
  exit /b 1
)

pushd "%ROOT%"

if not exist test\output\layered_device mkdir test\output\layered_device
echo Running layered_device...
"%EXE%" --config test\main_layered_device.ini --macro test\macros\test_layered_device_full.mac --output test\output\layered_device --run-name test_layered_device > test\output\layered_device\run.log 2>&1
if errorlevel 1 (
  type test\output\layered_device\run.log
  popd
  exit /b 1
)

if not exist test\output\hierarchical mkdir test\output\hierarchical
echo Running hierarchical...
"%EXE%" --config test\main_hierarchical.ini --macro test\macros\test_hierarchical_full.mac --output test\output\hierarchical --run-name test_hierarchical > test\output\hierarchical\run.log 2>&1
if errorlevel 1 (
  type test\output\hierarchical\run.log
  popd
  exit /b 1
)

popd
echo All G4UniversalSim end-to-end tests completed.
