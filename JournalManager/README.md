# Daily Journal Manager

A Python-based tool that automates daily Obsidian journal entries by:
- Creating new entries from a template
- Adding references to previous entries
- Carrying over incomplete tasks from previous entries
- Generating summaries of past entries using a local LLM

## Quick Start

1. **Run manually**: 
   ```
   python daily-journal-manager.py
   ```

2. **Run as scheduled service**:
   - Double-click `run_with_delay.bat` to start in background
   - Runs daily at 8:00 AM via APScheduler

3. **Check status**:
   - Double-click `check_status.bat` to see if service is running

4. **Setup auto-start**:
   - Double-click `create_startup_shortcut.bat` to add to Windows startup

## Configuration

Edit `config-file.json` to configure:
- Obsidian directory paths
- Template location
- LLM settings for summaries

## Features

- **Smart gap detection**: Properly handles periods when your computer is off
- **Task carryover**: Moves uncompleted tasks from your last entry to today's entry
- **Git integration**: Optional version control for your journal entries
- **LLM-powered insights**: Uses local LLMs to generate summaries of past entries

## Troubleshooting

If the script fails to create or update files:
1. Check the log file (`daily_journal_manager.log`) for errors
2. Verify template path in config is correct
3. Make sure Obsidian paths exist
4. Restart the scheduler by running `run_with_delay.bat`