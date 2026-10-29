@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   SONIQ MAX VST 2.4 DSP Plugin Builder
echo ===================================================
echo.

cd /d "%~dp0"
set SRC=src\SoniqMaxDSP.cpp
set OUT=bin\SoniqMaxDSP.dll
set APO_VST_DIR=C:\Program Files\EqualizerAPO\VSTPlugins

if not exist bin mkdir bin

:: 1. Check for MSVC (cl.exe)
where cl.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo [FOUND] Microsoft Visual C++ Compiler (cl.exe)
    echo Compiling SoniqMaxDSP.dll...
    cl.exe /LD /O2 /EHsc /std:c++17 /Isrc /Fe:"%OUT%" "%SRC%"
    goto :INSTALL
)

:: 2. Check for MinGW / GCC (g++)
where g++ >nul 2>&1
if %errorlevel% equ 0 (
    echo [FOUND] GNU C++ Compiler (g++)
    echo Compiling SoniqMaxDSP.dll...
    g++ -O3 -shared -std=c++17 -Isrc -o "%OUT%" "%SRC%" -static-libgcc -static-libstdc++ -Wl,--kill-at
    goto :INSTALL
)

:: 3. Check for Clang (clang++)
where clang++ >nul 2>&1
if %errorlevel% equ 0 (
    echo [FOUND] LLVM Clang++
    echo Compiling SoniqMaxDSP.dll...
    clang++ -O3 -shared -std=c++17 -Isrc -o "%OUT%" "%SRC%"
    goto :INSTALL
)

echo [ERROR] No C++ compiler (MSVC cl.exe, g++, or clang++) found on PATH.
echo.
echo To build SoniqMaxDSP.dll, please install either:
echo   1. Visual Studio Community (with C++ Desktop development)
echo      Run "Developer Command Prompt for VS" and run this batch file.
echo   2. MinGW-w64 (GCC for Windows)
echo.
pause
exit /b 1

:INSTALL
if exist "%OUT%" (
    echo.
    echo [SUCCESS] Compiled successfully: %OUT%
    echo.
    if exist "%APO_VST_DIR%" (
        echo Deploying to Equalizer APO VSTPlugins directory...
        copy /y "%OUT%" "%APO_VST_DIR%\SoniqMaxDSP.dll" >nul
        if %errorlevel% equ 0 (
            echo [INSTALLED] Copied to %APO_VST_DIR%\SoniqMaxDSP.dll
        ) else (
            echo [WARNING] Could not copy directly (requires Administrator privileges).
            echo Please manually copy %OUT% to:
            echo   %APO_VST_DIR%\SoniqMaxDSP.dll
        )
    )
    echo.
    echo All done!
) else (
    echo [FAILED] Compilation failed.
)
pause
