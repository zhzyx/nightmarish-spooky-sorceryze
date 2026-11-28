@echo off
set "ENGINE=%~dp0..\..\bin\godot.windows.editor.x86_64.exe"
if not exist "%ENGINE%" (
    echo Build the Windows editor with tools\build_gonggong_editor.ps1 first.
    pause
    exit /b 1
)
start "" "%ENGINE%" --path "%~dp0." --windowed --resolution 1440x810
