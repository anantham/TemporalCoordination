import requests
import json
import os
import logging
import traceback
import sys
from datetime import datetime, timedelta

# Configuration
# API key can be provided via:
# 1. Command line argument (python limitless_sync.py YOUR_API_KEY)
# 2. Environment variable (LIMITLESS_API_KEY)
# 3. Direct input when prompted

# Parse command line argument if provided
if len(sys.argv) > 1:
    API_KEY = sys.argv[1]
else:
    # Try to get from environment variable
    API_KEY = os.environ.get('LIMITLESS_API_KEY', '')
    print(API_KEY)
    # If still not set, prompt for it
    if not API_KEY:
        API_KEY = input("Enter your Limitless API key: ")

# Other configuration
BASE_URL = 'https://api.limitless.ai/v1/lifelogs'

# Get timezone from environment or use default
TIMEZONE = os.environ.get('LIMITLESS_TIMEZONE', 'America/New_York')

# Allow custom save directory via environment variable
custom_dir = os.environ.get('LIMITLESS_SAVE_DIR', '')
if custom_dir:
    SAVE_DIR = custom_dir
    # Make sure it exists
    os.makedirs(SAVE_DIR, exist_ok=True)
else:
    # Default to a subdirectory of the script location
    SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limitless_data')

# Allow for a backup/secondary save location
BACKUP_DIR = os.environ.get('LIMITLESS_BACKUP_DIR', '')
if BACKUP_DIR:
    # Make sure it exists
    os.makedirs(BACKUP_DIR, exist_ok=True)

SYNC_INTERVAL_DAYS = 1  # Default sync interval if no last_sync file exists
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limitless_sync.log')
LAST_SYNC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.last_sync')

# Set up logging with rotation
# Import the rotating file handler
from logging.handlers import RotatingFileHandler

# Configure root logger
# We're using RotatingFileHandler instead of FileHandler for automatic log rotation
rotating_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB max file size
    backupCount=5,             # Keep 5 backup files (limitless_sync.log.1, .2, etc.)
    encoding='utf-8'           # Ensure proper encoding for any unicode characters
)

# Set formatter for both handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s')
rotating_handler.setFormatter(formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        rotating_handler,    # Rotating file handler for log rotation
        console_handler      # Console handler for terminal output
    ]
)

# Create logger for this module
logger = logging.getLogger('limitless_sync')
logger.setLevel(logging.DEBUG)

# Also enable detailed logging for requests library
requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.DEBUG)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.DEBUG)

# Log script start with environment details
logger.info("-" * 80)
logger.info("STARTING LIMITLESS SYNC SCRIPT")
logger.info(f"Python version: {sys.version}")
logger.info(f"Script path: {__file__}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Primary save directory: {SAVE_DIR}")
if BACKUP_DIR:
    logger.info(f"Backup save directory: {BACKUP_DIR}")
logger.info(f"Timezone setting: {TIMEZONE}")
logger.info(f"API key (masked): {API_KEY[:4]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
logger.info("-" * 80)

# Ensure the save directory exists
try:
    os.makedirs(SAVE_DIR, exist_ok=True)
    logger.info(f"Verified save directory exists: {SAVE_DIR}")
except Exception as e:
    logger.critical(f"Failed to create save directory: {e}", exc_info=True)
    sys.exit(1)

def fetch_lifelogs(start_date, end_date):
    """Fetch life logs from the Limitless API for the specified date range."""
    logger.info(f"Fetching lifelogs from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    try:
        params = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d'),
            'timezone': TIMEZONE,
            'limit': 100  # Adjust as needed
        }
        headers = {
            'X-API-Key': API_KEY
        }
        
        logger.debug(f"Request parameters: {params}")
        logger.debug(f"Request URL: {BASE_URL}")
        logger.debug(f"Using API key: {API_KEY[:4]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
        
        response = requests.get(BASE_URL, params=params, headers=headers)
        
        logger.debug(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        
        # Log detailed error information if request failed
        if response.status_code != 200:
            logger.error(f"API request failed with status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            response.raise_for_status()
            
        # Log success and response summary
        data = response.json()
        item_count = len(data) if isinstance(data, list) else "N/A"
        logger.info(f"Successfully fetched data: {item_count} items retrieved")
        
        # Log truncated response content for debugging
        response_preview = str(data)[:500] + "..." if len(str(data)) > 500 else str(data)
        logger.debug(f"Response content preview: {response_preview}")
        
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching data: {e}")
        logger.error(f"Error details:", exc_info=True)
        if 'response' in locals():
            logger.error(f"Response status code: {response.status_code}")
            logger.error(f"Response headers: {response.headers}")
            logger.error(f"Response content: {response.text}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching data: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return None

def save_lifelogs(data, date):
    """Save the retrieved life logs to JSON files in primary and backup locations."""
    if not data:
        logger.warning("No data to save")
        return
    
    logger.info(f"Saving lifelogs data for date: {date}")
    
    # Create unique filename with timestamp to avoid overwrites
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'lifelogs_{date}_{timestamp}.json'
    
    # Save to primary location
    try:
        primary_path = os.path.join(SAVE_DIR, filename)
        logger.debug(f"Saving data to primary file: {primary_path}")
        logger.debug(f"Data type: {type(data)}")
        logger.debug(f"Data size (approx): {len(str(data))} characters")
        
        with open(primary_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        file_size = os.path.getsize(primary_path)
        logger.info(f"Data saved successfully to {primary_path} ({file_size} bytes)")
        
        # Update last sync date
        save_last_sync_date(datetime.now())
    except Exception as e:
        logger.error(f"Error saving data to primary location: {e}")
        logger.error("Detailed traceback:", exc_info=True)
    
    # Save to backup location if configured
    if BACKUP_DIR:
        try:
            backup_path = os.path.join(BACKUP_DIR, filename)
            logger.debug(f"Saving data to backup file: {backup_path}")
            
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            file_size = os.path.getsize(backup_path)
            logger.info(f"Data saved successfully to backup location: {backup_path} ({file_size} bytes)")
        except Exception as e:
            logger.error(f"Error saving data to backup location: {e}")
            logger.error("Detailed traceback:", exc_info=True)

def get_last_sync_date():
    """Get the last successful sync date from file.
    
    Returns:
        datetime: The last sync date or None if file doesn't exist
    """
    try:
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, 'r') as f:
                date_str = f.read().strip()
                last_sync = datetime.strptime(date_str, "%Y-%m-%d")
                logger.info(f"Found last sync date: {last_sync.strftime('%Y-%m-%d')}")
                return last_sync
        else:
            logger.info("No last sync file found, using default interval")
            return None
    except Exception as e:
        logger.error(f"Error reading last sync date: {e}")
        logger.error("Detailed traceback:", exc_info=True)
        return None

def save_last_sync_date(sync_date):
    """Save the current sync date to file.
    
    Args:
        sync_date (datetime): The date to save
    """
    try:
        date_str = sync_date.strftime("%Y-%m-%d")
        logger.info(f"Saving last sync date: {date_str}")
        
        with open(LAST_SYNC_FILE, 'w') as f:
            f.write(date_str)
            
        logger.info(f"Last sync date saved to {LAST_SYNC_FILE}")
    except Exception as e:
        logger.error(f"Error saving last sync date: {e}")
        logger.error("Detailed traceback:", exc_info=True)

def main():
    """Main function to execute the synchronization process."""
    logger.info("Starting Limitless data synchronization process")
    
    try:
        today = datetime.now()
        
        # Get the last sync date from file or use default interval
        stored_last_sync = get_last_sync_date()
        
        if stored_last_sync:
            # Calculate days since last sync
            days_since_last_sync = (today.date() - stored_last_sync.date()).days
            
            if days_since_last_sync <= 0:
                logger.info("Already synced today, but continuing anyway")
                last_sync_date = today - timedelta(days=1)  # Get at least today's data
            else:
                logger.info(f"Days since last sync: {days_since_last_sync}")
                last_sync_date = stored_last_sync
                
                # Safety check - don't fetch more than 30 days at once to avoid API limits
                if days_since_last_sync > 30:
                    logger.warning(f"More than 30 days since last sync ({days_since_last_sync}), limiting to 30 days")
                    last_sync_date = today - timedelta(days=30)
        else:
            # No previous sync record found, use default interval
            last_sync_date = today - timedelta(days=SYNC_INTERVAL_DAYS)
            logger.info(f"No last sync record found, using default interval: {SYNC_INTERVAL_DAYS} days")
        
        logger.info(f"Today's date: {today.strftime('%Y-%m-%d')}")
        logger.info(f"Fetching data since: {last_sync_date.strftime('%Y-%m-%d')}")
        
        data = fetch_lifelogs(last_sync_date, today)
        
        if data:
            logger.info("Data retrieved successfully, proceeding to save")
            save_lifelogs(data, today.strftime('%Y-%m-%d'))
            logger.info("Synchronization process completed successfully")
        else:
            logger.warning("No data was retrieved from the API")
            
    except Exception as e:
        logger.error(f"Unexpected error during synchronization: {e}")
        logger.error("Detailed error traceback:", exc_info=True)
        
    finally:
        logger.info("Synchronization process finished")
        logger.info("-" * 80)

if __name__ == '__main__':
    try:
        # Check if API key is provided and valid
        if not API_KEY or API_KEY == 'YOUR_API_KEY':
            logger.error("No valid API key provided. Please provide your Limitless API key.")
            print("ERROR: No valid API key provided.")
            print("You can provide your API key in one of these ways:")
            print("1. Command line argument: python limitless_sync.py YOUR_API_KEY")
            print("2. Environment variable: export LIMITLESS_API_KEY=YOUR_API_KEY")
            print("3. When prompted during script execution")
            sys.exit(1)
            
        main()
        
        # Get last sync date for display
        last_sync = get_last_sync_date()
        last_sync_str = last_sync.strftime("%Y-%m-%d") if last_sync else "unknown"
        
        print("=" * 60)
        print("Limitless data synchronization completed successfully.")
        print(f"Last sync date recorded: {last_sync_str}")
        print(f"Next sync will start from this date automatically.")
        if BACKUP_DIR:
            print(f"Data saved to both primary and backup locations.")
        print(f"Check the log file for details: {LOG_FILE}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        print("\nScript interrupted by user.")
    except Exception as e:
        logger.critical(f"Fatal error in main program: {e}")
        logger.critical("Detailed error traceback:", exc_info=True)
        print(f"Fatal error: {e}")
        print(f"See log file for details: {LOG_FILE}")
        sys.exit(1)