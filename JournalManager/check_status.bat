@echo off
echo Daily Journal Manager Status Checker
echo ================================
echo.

REM Check if the process is running
tasklist /fi "imagename eq pythonw.exe" /fo table /nh | findstr /i python > nul
if %ERRORLEVEL% EQU 0 (
    echo STATUS: RUNNING
    echo The Daily Journal Manager is currently running in the background.
) else (
    echo STATUS: NOT RUNNING
    echo The Daily Journal Manager is not currently running.
    echo You may want to run the script manually by double-clicking run_with_delay.bat
)

echo.
echo Last log entries:
echo ----------------
powershell -Command "Get-Content '%~dp0daily_journal_manager.log' -Tail 10"

echo.
echo Startup status:
echo --------------
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DailyJournalManager.lnk" (
    echo The script is configured to start automatically with Windows.
) else (
    echo The script is NOT configured to start automatically with Windows.
    echo Run create_startup_shortcut.bat to enable auto-start.
)

echo.
echo Press any key to exit...
pause > nul