# 🧠 CLAUDE'S PERSONAL NOTES

> 📝 **Note to self**: This file is MY personal scratchpad with insights about this codebase. READMEs are for humans!

## 🗺️ Navigation Cheat Sheet

Super long OneDrive path 😵‍💫 - I should use this shortcut instead:

```
C:\Ongoing\LLMs\TemporalCoordination
```

This is a junction point pointing to:
```
C:\Users\adity\OneDrive - Indian Institute of Science\Documents\Ongoing\LLMs\TemporalCoordination
```

## 📊 Project Components

### 📓 JournalManager
This is where I've put most work recently! It:
- Creates daily markdown files in Obsidian
- Carries over unfinished tasks
- Runs the Limitless data sync (added Mar 2025)
- Supports dual directory saving for redundancy 
- Has scheduled+manual modes

### 📱 Lifelog
- Just integrated this with JournalManager! 
- Gets personal data from Limitless.ai API
- Smart enough to recover after missed runs 
- Uses `.last_sync` file to track progress
- Backs up data to two locations now

### 🪄 Grimoire
> Note: Different Claude instance handles this codebase!
> Don't make changes here without coordination

## 🛠️ Quick Commands

When Adity asks for common functions:

| Task | What to Run | Notes |
|------|-------------|-------|
| Manual journal run | `run_with_delay.bat` | Shows output window, waits for user |
| Background journal run | `run_scheduled.bat` | No visible window, APScheduler |
| Check status | `check_status.bat` | Shows service status, logs, startup setup |
| Enable auto-start | `create_startup_shortcut.bat` | Sets Windows startup entry |

## 💡 Cool Features I've Added

1. 🔄 **Smart recovery system** - Automatically catches up on missed days when computer sleeps through run time
2. 📂 **Dual directory saves** - Every lifelog file gets saved to Obsidian folder AND backup location
3. 📝 **Task carryover detection** - Finds unfinished tasks with regex and moves them forward
4. 🪟 **Interactive run mode** - Created user-friendly batch file that shows progress
5. 🔍 **Run type tracking** - Added "MANUAL" vs "SCHEDULED" tags in logs for debugging

## ⚙️ Config Options

The `config-file.json` is where everything happens:

```json
{
  "run_limitless_sync": true,            // Enable/disable Limitless syncing
  "limitless_api_key": "abc123...",      // API authentication
  "limitless_save_dir": "C:\\path\\to\\primary",     // Main save location
  "limitless_backup_dir": "C:\\path\\to\\backup",    // 2nd save location
  "use_7day_summary": false,             // LLM summary features
  "use_30day_summary": false
}
```

## 🚨 Common Gotchas & How I Fixed Them

1. **Unicode log errors** - Windows console doesn't like emoji logs by default
   → Fix: `chcp 65001` or use Windows Terminal

2. **Stuck timezone setting** - Hard-coded 'America/New_York' in limitless_sync.py
   → No fix yet, would need config option

3. **Sleep recovery limits** - APScheduler has 30-day limit on missed data recovery
   → Added safety check in code

4. **Path formatting issues** - Windows paths need consistent handling
   → Always use `os.path.join()` or pathlib

5. **Directory missing errors** - Fixed with `os.makedirs(dir, exist_ok=True)`

## 💭 Ideas For Next Time

- [ ] Add Telegram Grimoire integration to daily summary
- [x] Implement log rotation (files get big over time) ✅ *Added Mar 2025*
- [ ] Create dashboard to visualize run statistics
- [ ] Customize Obsidian template selection
- [ ] Add timezone config for Limitless API

## 📝 Recent Improvements

### Log Rotation (March 2025)
Added `RotatingFileHandler` to both scripts:
- 5MB file size limit
- 5 backup files retained
- Unicode support
- Automatic rotation

### Enhanced Batch File (March 2025)
- Added color coding for success/error states
- Captures exit code for better status reporting
- Uses different colors for different information types
- Better visual structure