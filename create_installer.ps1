# Robot Control - PowerShell Installer Creator
# Creates a self-contained setup script + packages everything into a zip-based installer

$AppName    = "RobotControl"
$AppDisplay = "Robot Control"
$DistDir    = "$PSScriptRoot\dist\$AppName"
$OutDir     = "$PSScriptRoot\dist"
$SetupScript = "$OutDir\Install_RobotControl.bat"

if (-not (Test-Path $DistDir)) {
    Write-Host "[ERROR] dist\RobotControl not found. Run build_exe.bat first." -ForegroundColor Red
    pause; exit 1
}

Write-Host "Creating installer script..." -ForegroundColor Cyan

# Write the installer batch that will be distributed
$installer = @'
@echo off
echo ================================================
echo   Robot Control - Installer
echo ================================================
echo.
echo Installing to: %LOCALAPPDATA%\RobotControl\
echo.

set INST=%LOCALAPPDATA%\RobotControl

:: Create install dir
if not exist "%INST%" mkdir "%INST%"

:: Copy all files from the zip next to this installer
set SRC=%~dp0RobotControl
if not exist "%SRC%" (
    echo [ERROR] RobotControl folder not found next to this installer.
    echo Make sure RobotControl folder and Install_RobotControl.bat are in the same folder.
    pause & exit /b 1
)

echo Copying files...
xcopy /E /I /Y /Q "%SRC%\*" "%INST%\" >nul

:: Create Desktop shortcut
echo Creating shortcuts...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Robot Control.lnk'); $s.TargetPath = '%INST%\RobotControl.exe'; $s.WorkingDirectory = '%INST%'; $s.Description = 'Robot Control System'; $s.Save()"

:: Create Start Menu shortcut
set MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs
if not exist "%MENU%\Robot Control" mkdir "%MENU%\Robot Control"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%MENU%\Robot Control\Robot Control.lnk'); $s.TargetPath = '%INST%\RobotControl.exe'; $s.WorkingDirectory = '%INST%'; $s.Save()"

:: Save uninstall script
echo @echo off > "%INST%\Uninstall.bat"
echo echo Removing Robot Control... >> "%INST%\Uninstall.bat"
echo powershell -NoProfile -Command "Remove-Item -Path '%INST%' -Recurse -Force" >> "%INST%\Uninstall.bat"
echo powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\Robot Control.lnk') -Force -ErrorAction SilentlyContinue" >> "%INST%\Uninstall.bat"
echo powershell -NoProfile -Command "Remove-Item '%MENU%\Robot Control' -Recurse -Force -ErrorAction SilentlyContinue" >> "%INST%\Uninstall.bat"
echo echo Uninstall complete. >> "%INST%\Uninstall.bat"
echo pause >> "%INST%\Uninstall.bat"

echo.
echo ================================================
echo   Installation complete!
echo   Desktop shortcut: Robot Control
echo   Start Menu: Robot Control
echo   To uninstall: %INST%\Uninstall.bat
echo ================================================
echo.
set /p LAUNCH="Launch Robot Control now? (Y/N): "
if /i "%LAUNCH%"=="Y" start "" "%INST%\RobotControl.exe"
pause
'@

# Write installer batch
[System.IO.File]::WriteAllText($SetupScript, $installer, [System.Text.Encoding]::Default)

Write-Host "Packaging files..." -ForegroundColor Cyan

# Create distribution folder structure
$PackageDir = "$OutDir\RobotControl_Package"
if (Test-Path $PackageDir) { Remove-Item $PackageDir -Recurse -Force }
New-Item -ItemType Directory -Path $PackageDir | Out-Null

# Copy app files
Copy-Item $DistDir -Destination "$PackageDir\RobotControl" -Recurse
Copy-Item $SetupScript -Destination "$PackageDir\Install_RobotControl.bat"

# Create README
@"
Robot Control - Installation Package
=====================================
1. Double-click Install_RobotControl.bat
2. Installation goes to: %LOCALAPPDATA%\RobotControl\
3. Desktop and Start Menu shortcuts created automatically

Phone access (same WiFi):
- Start Robot Control on PC
- Phone browser: http://[PC-IP]:5000/mobile
- Or install the Android APK from the android/ folder
"@ | Out-File "$PackageDir\README.txt" -Encoding UTF8

# Compress to ZIP
$ZipPath = "$OutDir\RobotControl_Setup.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath }
Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  Done! Distribution package created:" -ForegroundColor Green
Write-Host "  $ZipPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Share this ZIP. Recipient extracts it and" -ForegroundColor Green
Write-Host "  double-clicks Install_RobotControl.bat" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
pause
