@echo off
chcp 65001 >nul
setlocal

rem ============================================================
rem  Image Horizontal Flip - drag and drop launcher
rem  Usage: drag an image file onto this .bat icon
rem ============================================================

set "HERE=%~dp0"
set "IMG=%~1"

if not defined IMG set /p "IMG=Drop an image here, or paste its path, then press Enter: "
if not defined IMG goto done

set "PY=C:\Python314\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%HERE%flip_image.py" "%IMG%" --auto-save
if errorlevel 1 echo   [ERROR] Check that the path is correct and the format is png / jpg / webp / bmp / gif.

:done
echo.
pause
