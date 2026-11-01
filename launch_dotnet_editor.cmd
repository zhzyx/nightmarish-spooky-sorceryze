@echo off
rem Launch the Godot editor with the repo-local .NET 10 SDK.
rem Without DOTNET_ROOT the editor falls back to the system .NET (9.x) and
rem reports "Unable to load .NET runtime, no compatible version was found".

setlocal
set "ROOT=%~dp0"
set "DOTNET_ROOT=%ROOT%.dotnet"
set "DOTNET_ROOT_X64=%DOTNET_ROOT%"
set "PATH=%DOTNET_ROOT%;%PATH%"

set "GODOT_EXE=%ROOT%bin\godot.windows.editor.dev.x86_64.clean01.mono.exe"
if not exist "%GODOT_EXE%" (
    echo [launch] Editor binary not found: "%GODOT_EXE%"
    echo [launch] Build it first, then re-run this script.
    exit /b 1
)

set "PROJECT=%~1"
if "%PROJECT%"=="" set "PROJECT=%~dp0samples\pong_csharp_debug"

echo [launch] DOTNET_ROOT = %DOTNET_ROOT%
echo [launch] project     = %PROJECT%
start "" "%GODOT_EXE%" --editor --path "%PROJECT%"
endlocal
