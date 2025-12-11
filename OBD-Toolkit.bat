@echo off
title OBD Toolkit
cd /d "%~dp0"

:: If no arguments provided, show interactive help
if "%~1"=="" (
    python -m obd_toolkit --help
    echo.
    echo ========================================
    echo  Double-click again or run with a command
    echo  Example: OBD-Toolkit.bat scan
    echo ========================================
    echo.
    pause
) else (
    python -m obd_toolkit %*
    if %errorlevel% neq 0 (
        echo.
        pause
    )
)
