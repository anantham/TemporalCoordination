@echo off
color 0E
echo ====================================================
echo     Creating startup shortcut for Daily Journal Manager
echo ====================================================
echo.

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_NAME=DailyJournalManagerScheduled.lnk
set SCRIPT_PATH=C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat

echo Creating a new batch file for scheduled runs...
echo @echo off > "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat"
echo echo Starting Daily Journal Manager with APScheduler in background... >> "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat"
echo start /B pythonw "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\daily-journal-manager.py" --scheduled >> "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat"
echo echo Started! Check daily_journal_manager.log for status. >> "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat"
echo exit >> "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\run_scheduled.bat"

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%STARTUP_FOLDER%\%SHORTCUT_NAME%'); $Shortcut.TargetPath = '%SCRIPT_PATH%'; $Shortcut.Save()"

echo.
echo Created startup shortcut in %STARTUP_FOLDER%
echo The Journal Manager will now start automatically on login with the scheduled mode.
echo.
echo IMPORTANT: The startup shortcut uses scheduled mode which runs in the background.
echo If you want to see output, use the run_with_delay.bat file instead.
echo.
pause