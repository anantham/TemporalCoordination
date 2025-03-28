@echo off
:: Enhanced color-coded version of Daily Journal Manager launcher

:: Set base color scheme (light green on black)
color 0A

echo ====================================================
echo        Daily Journal Manager Launcher
echo ====================================================
echo.

:: Show date in bright white
echo [%date% %time%]
echo Current path: %cd%
echo.

:: Bright green for status
color 0A
echo [1] Starting Daily Journal Manager in manual mode...
echo.

:: Run the script and capture the exit code
python "C:\Ongoing\LLMs\TemporalCoordination\JournalManager\daily-journal-manager.py"
set ERRORLEVEL_BACKUP=%ERRORLEVEL%

echo.
if %ERRORLEVEL_BACKUP% EQU 0 (
    :: Success - bright green
    color 0A
    echo [SUCCESS] Daily Journal Manager execution completed!
) else (
    :: Error - bright red
    color 0C
    echo [ERROR] Daily Journal Manager execution failed with code %ERRORLEVEL_BACKUP%!
)

:: Reset to standard color
color 07
echo.
echo Log file location:
echo C:\Ongoing\LLMs\TemporalCoordination\JournalManager\daily_journal_manager.log
echo.

:: Yellow for important info
color 0E
echo Check the log file for complete details about the execution.
echo.
echo ====================================================
echo.

:: Reset to standard color before pause
color 07
pause
echo Closing window...