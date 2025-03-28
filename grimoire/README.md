# Telegram Grimoire

A secure interface for accessing and manipulating Telegram messages using the MTProto API.

## Setup

1. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/macOS
   python -m venv venv
   source venv/bin/activate
   ```

2. **Install Requirements**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set Environment Variables**
   ```bash
   cp .env.template .env
   ```
   Edit `.env` to add your credentials:
   - Get API credentials at https://my.telegram.org/apps
   - Add your API_ID and API_HASH values

3. **Run Test Script**
   ```bash
   python fetch_saved_messages.py
   ```
   The first time you run this, you'll be prompted to authenticate via Telegram.

## Security Notes

- Never commit your `.env` file or session files (`.session`) to version control
- The `.gitignore` file is configured to prevent accidental commits of sensitive data
- Regenerate your API credentials if you suspect they've been compromised

## Features

- **fetch_saved_messages.py**: Updates your saved messages JSON file with new messages from Telegram

  **Features:**
  - Syncs your result.json file with your latest Saved Messages
  - Automatically detects the latest message date and only fetches newer messages
  - Option to keep running and monitor for new messages in real-time
  - Creates backups of your existing JSON file for safety
  - Supports all message types (text, photos, documents, stickers, etc.)
  
  **Usage:**
  ```bash
  # One-time sync to update result.json with new messages
  python fetch_saved_messages.py
  
  # Specify a different JSON file
  python fetch_saved_messages.py --json_file custom_path.json
  
  # Create a backup before updating
  python fetch_saved_messages.py --backup
  
  # Keep running and monitor for new messages with polling (every 5 minutes by default)
  python fetch_saved_messages.py --monitor
  
  # Set custom batch size for fetching messages (to avoid rate limits)
  python fetch_saved_messages.py --batch-size 50
  
  # Set custom delay between batches in seconds (for rate limit compliance)
  python fetch_saved_messages.py --batch-delay 5
  
  # Set custom polling interval for monitoring mode in seconds
  python fetch_saved_messages.py --monitor --polling-interval 120
  ```
  
  **API-Friendly Features:**
  - Fetches messages in small batches (default: 100) with delays between batches
  - Uses proper pagination instead of trying to get all messages at once
  - Handles rate limiting with automatic backoff when Telegram requests it
  - Implements adaptive polling that slows down when no new messages are found
  - Properly manages handler resources to avoid session termination
  - Prevents duplicate messages by tracking message IDs
  - Stops fetching early once it detects messages already in the JSON
  
  **Avoiding Session Termination:**
  ```bash
  # Use minimal workers to avoid triggering Telegram security measures
  python fetch_saved_messages.py --workers 1
  
  # For a one-time sync that's gentle on the API (recommended for daily use)
  python fetch_saved_messages.py --workers 1 --batch-size 50 --batch-delay 5
  ```
  
  The default Pyrogram configuration creates 20 worker threads which can trigger Telegram's security measures 
  and cause you to be logged out of all sessions. Using `--workers 1` (the minimum allowed) is strongly recommended.
  ```

## Data Analysis Tools

Several Python scripts are available to analyze Telegram data exports:

### 1. analyze_json.py
A general-purpose JSON analyzer that examines the structure, metadata, and statistics of any JSON file.

**Usage:**
```bash
python analyze_json.py [path_to_json_file]
```

### 2. telegram_analyzer.py
A specialized analyzer for Telegram export data that provides detailed statistics about:
- Message metadata (total messages, date range, daily averages)
- Time patterns (hourly/daily/monthly activity)
- Content analysis (text messages, media types, URLs)
- User activity (message counts, words per message)

**Usage:**
```bash
python telegram_analyzer.py [path_to_telegram_json]
```

### 3. visualize_telegram_data.py
Creates visualizations from the Telegram data, generating PNG images showing:
- Messages per day/month with trend lines
- Hourly activity patterns
- Weekday activity patterns
- Message and media type distributions
- Text length and word count distributions
- Common words analysis

**Requirements:**
```bash
pip install matplotlib numpy
```

### 4. telegram_to_dataframe.py
Converts Telegram message data to pandas DataFrame and saves it as CSV and Excel files for further analysis.

**Features:**
- Extracts message timestamps and text content
- Handles various Telegram message format structures
- Creates additional time columns (hour, weekday, month, year)
- Saves to both CSV and Excel formats

**Requirements:**
```bash
pip install pandas openpyxl
```

**Usage:**
```bash
python telegram_to_dataframe.py [path_to_telegram_json]
```

### 5. telegram_to_csv.py
A simpler alternative that exports Telegram messages to CSV without pandas dependency (uses only Python standard library).

**Features:**
- Works without any additional dependencies
- Extracts message timestamps and text content
- Handles various Telegram message format structures
- Creates additional time columns (hour, weekday, month, year)
- Creates a clean CSV file that can be opened in any spreadsheet program

**Usage:**
```bash
python telegram_to_csv.py [path_to_telegram_json]
```

### 6. telegram_prayer_analyzer.py
Identifies prayer patterns in Telegram messages using a local Ollama LLM and saves to DataFrame.

**Features:**
- Uses Ollama API to analyze messages for prayer patterns
- Privacy-preserving (all analysis happens locally)
- Configurable to process only a subset of messages
- Creates a pandas DataFrame with prayer analysis results
- Exports to both CSV and Excel formats
- Analyze JSON structure with detailed message type breakdowns

**Requirements:**
```bash
pip install pandas requests
```

**Usage:**
```bash
# Prayer analysis mode
python telegram_prayer_analyzer.py --json result.json --prayers "Prayer Wishlist Aditya.txt" --model llama3.2:latest --max 10

# JSON structure analysis mode
python telegram_prayer_analyzer.py --json result.json --analyze-structure --samples 5
```

### 7. telegram_prayer_csv.py
A simpler version of the prayer analyzer that uses only Python standard library (no pandas).

**Features:**
- Works without pandas dependency
- Uses Ollama API for local, privacy-preserving prayer analysis
- Configurable to process a specific number of recent messages
- Exports results directly to CSV
- Parses prayer components into separate columns (prayer_type, prayer_arg1, prayer_arg2)
- Handles Chain-of-Thought model responses with improved extraction logic

**Requirements:**
```bash
pip install requests
```

**Usage:**
```bash
python telegram_prayer_csv.py --json result.json --prayers "Prayer Wishlist Aditya.txt" --model llama3.2:latest --max 10
```

**Advanced options:**
```bash
# Continue analyzing where you left off, skipping already processed messages
python telegram_prayer_csv.py --json result.json --max 100 --continue

# Re-analyze all messages, overwriting previous results
python telegram_prayer_csv.py --json result.json --max 100 --reanalyze

# Customize the fixed context window (default: 3 messages before, 2 after)
python telegram_prayer_csv.py --json result.json --context-before 5 --context-after 3

# Use dynamic AI-driven context selection!
python telegram_prayer_csv.py --json result.json --smart-context --max-context-before 10 --max-context-after 10

# Enable verbose logging to see model inputs and outputs
python telegram_prayer_csv.py --json result.json --verbose
```

**Smart Context Selection:**
The script can use the LLM itself to determine which surrounding messages are relevant for understanding if a target message contains a prayer:

1. First, it collects up to 10 messages before and after the target (customizable)
2. It then sends these to the LLM asking it to identify which ones are actually relevant
3. Only the truly relevant context messages are used for prayer detection
4. This creates a dynamic, message-specific context window for more accurate analysis

**Enhanced Model Handling:**
The script now has improved handling of various model response formats:
1. Handles verbose Chain-of-Thought (CoT) reasoning with `<think>...</think>` tags
2. Extracts proper bracketed prayer format from responses
3. Correctly processes ambiguous or non-standard model outputs
4. Parses prayer responses into components (type, arg1, arg2) for detailed analysis

**Streamlined CSV Output:**
- Focused columns for readability (date, time, text, prayer analysis)
- Prayer components separated into individual columns 
- Technical metadata fields removed for cleaner output

**Robust features:**
- Automatic retry with exponential backoff for API timeouts or connection issues
- Ability to continue analysis from where you left off
- Skip or re-analyze previously processed messages
- Contextual prayer detection using surrounding messages for better accuracy
- Smart context selection that dynamically adapts to each message
- Verbose logging mode for debugging model responses

**Note:** Both prayer analysis scripts require:
1. [Ollama](https://ollama.ai/download) to be installed and running
2. The specified model to be pulled (e.g., `ollama pull llama3.2:latest`)

## Future Development

- Message automation
- Scheduled message processing
- Advanced content analysis
- Custom command handling

### Current Issues

1) How to ensure local cache of messages are upto date with telegram without triggering telegram's [log you out from all devices](https://github.com/LonamiWebs/Telethon/issues/4051#issuecomment-1461514786) protection mechanism. 


