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

:: 1. Check if 64-bit compiler is already on current PATH
where cl.exe >nul 2>&1
if %errorlevel% equ 0 goto :COMPILE_MSVC

where g++ >nul 2>&1
if %errorlevel% equ 0 goto :COMPILE_GCC

where clang++ >nul 2>&1
if %errorlevel% equ 0 goto :COMPILE_CLANG

:: 2. Check for WinLibs MinGW-w64 (64-bit) via WinGet
for /d %%W in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs*") do (
    if exist "%%W\mingw64\bin\g++.exe" (
        echo [FOUND] WinLibs MinGW-w64 [64-bit] at: %%W\mingw64\bin
        set "PATH=%%W\mingw64\bin;!PATH!"
        goto :COMPILE_GCC
    )
)

:: 3. Auto-detect Visual Studio via vswhere or standard directories
set VSWHERE="%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist %VSWHERE% (
    for /f "usebackq tokens=*" %%i in (`%VSWHERE% -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set "VS_DIR=%%i"
    )
    if defined VS_DIR (
        if exist "!VS_DIR!\VC\Auxiliary\Build\vcvars64.bat" (
            echo [FOUND] Visual Studio at: "!VS_DIR!"
            call "!VS_DIR!\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
            goto :COMPILE_MSVC
        )
    )
)

:: Check common VS 2022 & 2019 install paths
for %%V in (
    "%ProgramFiles%\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles%\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
) do (
    if exist %%V (
        echo [FOUND] Visual Studio environment: %%~V
        call %%V >nul 2>&1
        goto :COMPILE_MSVC
    )
)

:: 4. Check common MinGW-w64 / MSYS2 64-bit paths
for %%M in (
    "C:\msys64\ucrt64\bin"
    "C:\msys64\mingw64\bin"
    "C:\mingw64\bin"
    "C:\MinGW\bin"
) do (
    if exist "%%~M\g++.exe" (
        echo [FOUND] MinGW GCC at: %%~M
        set "PATH=%%~M;!PATH!"
        goto :COMPILE_GCC
    )
)

echo [ERROR] No C++ compiler found.
echo.
echo To build SoniqMaxDSP.dll, please install either:
echo   1. WinLibs MinGW-w64 [run: winget install BrechtSanders.WinLibs.POSIX.UCRT]
echo   2. Visual Studio Community [with C++ Desktop development workload]
echo.
pause
exit /b 1

:COMPILE_MSVC
echo [FOUND] Microsoft Visual C++ Compiler [cl.exe]
echo Compiling SoniqMaxDSP.dll [64-bit]...
cl.exe /LD /O2 /EHsc /std:c++17 /Isrc /Fe:"%OUT%" "%SRC%"
goto :INSTALL

:COMPILE_GCC
echo [FOUND] GNU C++ Compiler [g++]
echo Compiling SoniqMaxDSP.dll [64-bit]...
g++ -O3 -shared -std=c++17 -Isrc -o "%OUT%" "%SRC%" -static-libgcc -static-libstdc++ -Wl,--kill-at
goto :INSTALL

:COMPILE_CLANG
echo [FOUND] LLVM Clang++
echo Compiling SoniqMaxDSP.dll [64-bit]...
clang++ -O3 -shared -std=c++17 -Isrc -o "%OUT%" "%SRC%"
goto :INSTALL

:INSTALL
if exist "%OUT%" (
    echo.
    echo ===================================================
    echo   [SUCCESS] Compiled SoniqMaxDSP.dll [64-bit]
    echo   Location: %~dp0%OUT%
    echo ===================================================
    echo.
    if exist "%APO_VST_DIR%" (
        echo Deploying to Equalizer APO VSTPlugins folder...
        copy /y "%OUT%" "%APO_VST_DIR%\SoniqMaxDSP.dll" >nul 2>&1
        if !errorlevel! equ 0 (
            echo [INSTALLED] Successfully copied to:
            echo   %APO_VST_DIR%\SoniqMaxDSP.dll
        ) else (
            echo [NOTICE] Direct copy to C:\Program Files requires Administrator privileges.
            echo SONIQ MAX will automatically load the plugin from your local build:
            echo   "%~dp0%OUT%"
            echo.
            echo Optional: To install system-wide, copy "%~dp0%OUT%"
            echo into: "%APO_VST_DIR%\SoniqMaxDSP.dll"
        )
    )
    echo.
    echo Equalizer APO will now automatically load SONIQ MAX DSP!
) else (
    echo [FAILED] Compilation failed.
)
echo.
