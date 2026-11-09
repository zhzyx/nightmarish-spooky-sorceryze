@echo off
setlocal
pushd "%~dp0" || exit /b 1
if exist "Maliang\godot.windows.editor.x86_64.exe" goto launch
set "staging=Maliang-unpack-%RANDOM%-%RANDOM%"
if exist "%staging%" goto failed
mkdir "%staging%" || goto failed
echo Enter the delivery password when prompted. Extraction is needed only once.
"extract\7z.exe" x -y "-o%staging%" "Maliang-Windows-x64.7z"
if errorlevel 1 goto cleanup
if not exist "%staging%\godot.windows.editor.x86_64.exe" goto cleanup
ren "%staging%" Maliang
if errorlevel 1 goto cleanup
:launch
start "" "Maliang\godot.windows.editor.x86_64.exe"
popd
exit /b 0
:cleanup
rmdir /s /q "%staging%"
if exist "Maliang\godot.windows.editor.x86_64.exe" goto launch
:failed
echo The editor could not be extracted. Check the password, free disk space and destination folder.
pause
popd
exit /b 1
