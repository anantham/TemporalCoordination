# Daily Journal Manager

A Python-based tool that automates daily Obsidian journal entries by:
- Creating new entries from a template
- Adding references to previous entries
- Carrying over incomplete tasks from previous entries
- Generating summaries of past entries using a local LLM
- Syncing with Limitless.ai for personal data tracking

## Quick Start

1. **Run manually**: 
   ```
   python daily-journal-manager.py
   ```
   Or double-click `run_with_delay.bat` for a color-coded interactive window

2. **Run as scheduled service**:
   - Uses APScheduler to run daily at 8:00 AM
   - Running `run_scheduled.bat` starts the scheduler in background mode

3. **Check status**:
   - Double-click `check_status.bat` to see if service is running
   - View recent log entries and startup configuration

4. **Setup auto-start**:
   - Double-click `create_startup_shortcut.bat` to add to Windows startup
   - Creates a shortcut to run in scheduled mode on system startup

## Configuration

Edit `config-file.json` to configure:
- Obsidian directory paths
- Template location
- LLM settings for summaries
- Limitless sync settings:
  - API key
  - Primary and backup save directories
  - Timezone settings (auto-detects by default)

## Features

- **Smart gap detection**: Properly handles periods when your computer is off
- **Task carryover**: Moves uncompleted tasks from your last entry to today's entry
- **Git integration**: Optional version control for your journal entries
- **LLM-powered insights**: Uses local LLMs to generate summaries of past entries
- **Log rotation**: Automatically rotates logs when they reach 5MB
- **Dual-directory backup**: Saves Limitless data to both primary and backup locations
- **Timezone auto-detection**: Detects system timezone for accurate data timestamps

## Troubleshooting

If the script fails to create or update files:
1. Check the log file (`daily_journal_manager.log`) for errors
2. Verify template path in config is correct
3. Make sure Obsidian paths exist
4. Restart the script by running `run_with_delay.bat`

## Requirements

- **Operating System:** Windows (could be adapted for macOS/Linux)
- **Python:** Python 3.6+
- **Dependencies:**
  - `apscheduler` - For task scheduling
  - `requests` - For LLM API calls and Limitless API
  - `tzlocal` - For timezone auto-detection (optional)
  
- **Local LLM Server:**  
  A server such as Ollama running on http://localhost:11434 serving a model (e.g., llama3.2).
  
- **Obsidian Setup:**  
  Your Obsidian vault should contain your daily notes folder and a template file.

## Scheduling Details

- **Background Mode:**  
  The script uses APScheduler to run in the background without requiring an open terminal.
  
- **Missed Job Handling:**  
  If your computer is asleep at the scheduled time, the task will run when your computer wakes up.
  
- **Logs:**  
  Check `daily_journal_manager.log` to verify successful execution.
  Logs automatically rotate at 5MB with 5 backup files preserved.

## Advanced Usage

- **Git Integration:**  
  Set `"use_git": true` in config to enable automatic Git commits of your journal changes.
  
- **Custom Summaries:**  
  Modify the summary prompts in the config file to customize the generated content.

- **Limitless Integration:**
  Set `"run_limitless_sync": true` and configure API key and directories to sync your Limitless.ai data.