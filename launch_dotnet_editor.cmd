@echo off
rem Launch the Godot editor with the repo-local .NET 10 SDK.
rem Without DOTNET_ROOT the editor falls back to the system .NET (9.x) and
rem reports "Unable to load .NET runtime, no compatible version was found".

setlocal
set "ROOT=%~dp0"
set "DOTNET_ROOT=%ROOT%.dotnet"
set "DOTNET_ROOT_X64=%DOTNET_ROOT%"
set "PATH=%DOTNET_ROOT%;%PATH%"

set "PROJECT=%~1"
if "%PROJECT%"=="" set "PROJECT=%~dp0samples\pong_csharp_debug"

echo [launch] DOTNET_ROOT = %DOTNET_ROOT%
echo [launch] project     = %PROJECT%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%tools\launch_gonggong_editor.ps1" -Project "%PROJECT%"
exit /b %ERRORLEVEL%
