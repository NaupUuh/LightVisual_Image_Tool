@echo off
chcp 65001 >nul
rem ===================================================================
rem  LightVisual Image Tool - chay AN, KHONG hien cua so cmd.
rem  Muon xem cua so cmd de doc loi:  go  run.bat debug
rem ===================================================================
cd /d "%~dp0"

if /i "%~1"=="debug" goto :run
if /i "%~1"=="hidden" goto :run

rem --- Chua an: tu goi lai chinh no qua 1 VBS tam de chay an ---
set "VBS=%TEMP%\lvi_hide_%RANDOM%%RANDOM%.vbs"
> "%VBS%" echo CreateObject("WScript.Shell").Run """%~f0"" hidden", 0, False
cscript //nologo "%VBS%" >nul 2>&1
del "%VBS%" >nul 2>&1
exit /b


:run
title LightVisual Image Tool

rem ===================================================================
rem  CHON PYTHON (>= 3.9)
rem  Tool chay duoc tu Python 3.9 (core dung urllib, khong can pip).
rem  Thu theo thu tu: py launcher -> duong dan co dinh -> PATH.
rem ===================================================================
set "PY="

call :try_py -3.13
call :try_py -3.12
call :try_py -3.11
call :try_py -3.10
call :try_py -3.9

if not defined PY if exist "C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe" set "PY=C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe"
if not defined PY if exist "C:\Users\Admin\.genfarmer\python-3.9.0.amd64\python.exe" set "PY=C:\Users\Admin\.genfarmer\python-3.9.0.amd64\python.exe"
if not defined PY set "PY=python"

"%PY%" main.py
if errorlevel 1 (
  echo.
  echo ===== LOI KHI CHAY =====
  pause
)
exit /b


:try_py
if defined PY exit /b
py %~1 -c "import sys" >nul 2>&1
if errorlevel 1 exit /b
for /f "delims=" %%P in ('py %~1 -c "import sys;print(sys.executable)"') do set "PY=%%P"
exit /b
