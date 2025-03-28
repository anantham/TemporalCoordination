# Temporal Coordination

This repository contains tools for managing and automating various time-based tasks.

## Components

### 1. [Journal Manager](./JournalManager)

Daily journal entry automation tool for Obsidian.

### 2. [Grimoire](./grimoire)

Telegram API integration for message handling and automation.

## Journal Manager Details

The **Daily Journal Manager** automatically:

- **Creates today's note** from a template if it doesn't already exist
- **Carries over incomplete tasks** from previous journal entries
- **Detects gaps** between entries when your computer has been off
- **Inserts appropriate references** to previous entries
- **Generates summaries** using a local language model
- **Adds modification timestamps** to track when entries were updated

## Features

- **Daily Note Creation:**  
  Copies a template to create today's note if it doesn't exist.
  
- **Task Carryover:**  
  Automatically carries over incomplete tasks from yesterday's note.

- **Yesterday's Note Reference:**  
  Inserts a reference line to yesterday's note for easy navigation.

- **Summaries:**  
  - **7-Day Summary:** Generates a summary of the past 7 days of journal entries using a local LLM.
  - **30-Day Summary:** Similarly, generates a summary for the past 30 days.
  
- **Automatic Scheduling:**  
  Runs automatically at a specified time (default: 8:00 AM) using APScheduler.
  
- **Git Integration:**  
  Optional version control for your journal entries.
  
- **Comprehensive Logging:**  
  Detailed logging of all operations for troubleshooting.

## Requirements

- **Operating System:** Windows (could be adapted for macOS/Linux)
- **Python:** Python 3.6+
- **Dependencies:**
  - `apscheduler` - For task scheduling
  - `requests` - For LLM API calls
  
- **Local LLM Server:**  
  A server such as Ollama running on http://localhost:11434 serving a model (e.g., llama3.2).
  
- **Obsidian Setup:**  
  Your Obsidian vault should contain your daily notes folder and a template file.

## Quick Access to Journal Manager

1. **Run Manually:**
   ```
   journal_launcher.bat
   ```

2. **Start Background Service:**  
   ```
   start_journal_service.bat
   ```
   
   The script will run at 8:00 AM daily, even if your computer was asleep at that time.

3. **Check Status:**  
   ```
   check_journal_status.bat
   ```
   - See if the script is running
   - View recent log entries
   - Verify auto-start configuration

4. **Setup Auto-start:**
   ```
   cd JournalManager
   create_startup_shortcut.bat
   ```

See the [Journal Manager README](./JournalManager/README.md) for detailed documentation.

## Scheduling Details

- **Background Mode:**  
  The script uses APScheduler to run in the background without requiring an open terminal.
  
- **Missed Job Handling:**  
  If your computer is asleep at the scheduled time, the task will run when your computer wakes up.
  
- **Logs:**  
  Check `daily_journal_manager.log` to verify successful execution.

## Advanced Usage

- **Git Integration:**  
  Set `"use_git": true` in config to enable automatic Git commits of your journal changes.
  
- **Custom Summaries:**  
  Modify the summary prompts in the config file to customize the generated content.
  
- **Windows Task Scheduler:**  
  For advanced scheduling, the script includes Windows Task Scheduler integration.