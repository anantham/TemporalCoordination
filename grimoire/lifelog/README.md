# Limitless Life Log Synchronization

This tool synchronizes your Limitless meeting transcripts and life logs to your Windows laptop.

## Setup Instructions

1. **Install Requirements**:
   ```
   pip install requests
   ```

2. **Set your API Key**:

   You can provide your API key in any of these three ways:
   
   - **Option 1**: Pass it as a command-line argument
     ```
     python initial_sync.py YOUR_API_KEY
     ```
   
   - **Option 2**: Set it as an environment variable
     ```
     # Windows Command Prompt
     set LIMITLESS_API_KEY=YOUR_API_KEY
     
     # Windows PowerShell
     $env:LIMITLESS_API_KEY="YOUR_API_KEY"
     
     # Linux/macOS
     export LIMITLESS_API_KEY=YOUR_API_KEY
     ```
   
   - **Option 3**: Enter it when prompted during script execution

3. **Initial Synchronization**:

   Run the initial sync script to fetch all data from March 1st onwards:
   ```
   python initial_sync.py
   ```

4. **Regular Synchronization**:

   After the initial sync, use the daily sync script to fetch recent data:
   ```
   python limitless_sync.py
   ```

5. **Scheduling Automatic Sync** (Windows):

   Using Task Scheduler:
   1. Open Task Scheduler
   2. Create a new Basic Task
   3. Choose "Daily" and set time to 9:00 AM
   4. Action: Start a program
   5. Program/script: Path to your Python executable
   6. Add arguments: Path to limitless_sync.py
   7. Finish

## Data Storage

Synchronized data is stored in the `limitless_data` folder with files named:
`lifelogs_YYYY-MM-DD_HHMMSS.json`

## Logs

All synchronization activities are logged to `limitless_sync.log` in the same directory.

## Troubleshooting

If synchronization fails:
1. Check `limitless_sync.log` for error messages
2. Verify your API key is correct
3. Check your internet connection
4. Ensure you have the `requests` library installed (`pip install requests`)