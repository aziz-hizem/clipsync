@echo off
echo ClipSync Windows Build Script
echo ============================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m pip install -r requirements.txt

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build executable
echo Building Windows executable...
python -m PyInstaller clip_sync.spec

REM Check if build was successful
if exist "dist\ClipSync.exe" (
    echo.
    echo Build completed successfully!
    echo Executable location: dist\ClipSync.exe
    echo.
    
    REM Create distribution ZIP
    echo Creating distribution package...
    powershell -Command "Compress-Archive -Path 'dist\*' -DestinationPath 'ClipSync-Windows.zip' -Force"
    if exist "ClipSync-Windows.zip" (
        echo Distribution package created: ClipSync-Windows.zip
    )
) else (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Press any key to exit...
pause >nul