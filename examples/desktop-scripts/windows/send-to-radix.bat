@echo off
setlocal enabledelayedexpansion
REM =========================================================================
REM  send-to-radix.bat
REM  Right-click "Send To" script for Windows.
REM  Uploads one or more rent roll files to the Radix Underwriting API.
REM
REM  Setup:
REM    1. Set your API key and email below.
REM    2. Press Win+R, type: shell:sendto
REM    3. Copy (or create a shortcut to) this .bat file into that folder.
REM    4. Right-click any .xlsx/.xls/.csv file(s) → Send To → send-to-radix
REM
REM  Dependencies: curl (ships with Windows 10+)
REM =========================================================================

REM --- Configuration (edit these) -------------------------------------------
set "API_KEY=riq_live_your_api_key_here"
set "NOTIFY_EMAIL=you@company.com"
set "API_URL=https://connect.rediq.io/api/external/v1/upload"
REM --------------------------------------------------------------------------

if "%API_KEY%"=="riq_live_your_api_key_here" (
    echo.
    echo  ERROR: Please edit this script and set your API_KEY.
    echo  Open %~f0 in a text editor and replace the placeholder.
    echo.
    pause
    exit /b 1
)

if "%~1"=="" (
    echo.
    echo  Usage: Drag files onto this script, or use "Send To".
    echo.
    pause
    exit /b 1
)

REM Build the curl command with all files
set "FILES="
set COUNT=0
for %%F in (%*) do (
    set /a COUNT+=1
    set "FILES=!FILES! -F "files=@%%~F""
)

echo.
echo  Radix Rent Roll Uploader
echo  ========================
echo  Uploading !COUNT! file(s)...
echo.

curl -s -X POST "%API_URL%" ^
  -H "Authorization: Bearer %API_KEY%" ^
  !FILES! ^
  -F "notificationMethod=[{\"type\":\"email\",\"entry\":\"%NOTIFY_EMAIL%\"}]" ^
  -o "%TEMP%\radix-response.json" ^
  -w "%%{http_code}" > "%TEMP%\radix-http-code.txt"

set /p HTTP_CODE=<"%TEMP%\radix-http-code.txt"

if "%HTTP_CODE%"=="202" (
    echo  Upload successful! (HTTP 202^)
    echo.
    echo  Response:
    type "%TEMP%\radix-response.json"
    echo.
    echo.
    echo  You will receive an email at %NOTIFY_EMAIL% when processing completes.
) else (
    echo  Upload FAILED (HTTP %HTTP_CODE%^)
    echo.
    type "%TEMP%\radix-response.json"
)

echo.
del "%TEMP%\radix-response.json" 2>nul
del "%TEMP%\radix-http-code.txt" 2>nul
pause


