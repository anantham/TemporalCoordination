import requests
import json
import os
import logging
import traceback
import sys
from datetime import datetime, timedelta

# Configuration
# API key can be provided via:
# 1. Command line argument (python initial_sync.py YOUR_API_KEY)
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
TIMEZONE = 'America/New_York'
SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limitless_data')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limitless_sync.log')

# Initial sync date (March 1, 2025)
INITIAL_SYNC_DATE = datetime(2025, 3, 1)

# Set up logging - super verbose
# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        # File handler
        logging.FileHandler(LOG_FILE),
        # Console handler
        logging.StreamHandler(sys.stdout)
    ]
)

# Create logger for this module
logger = logging.getLogger('initial_sync')
logger.setLevel(logging.DEBUG)

# Also enable detailed logging for requests library
requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.DEBUG)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.DEBUG)

# Log script start with environment details
logger.info("=" * 80)
logger.info("STARTING INITIAL LIMITLESS SYNC SCRIPT")
logger.info(f"Python version: {sys.version}")
logger.info(f"Script path: {__file__}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Save directory: {SAVE_DIR}")
logger.info(f"Timezone setting: {TIMEZONE}")
logger.info(f"Initial sync date: {INITIAL_SYNC_DATE.strftime('%Y-%m-%d')}")
logger.info(f"API key (masked): {API_KEY[:4]}...{API_KEY[-4:] if len(API_KEY) > 8 else ''}")
logger.info("=" * 80)

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
        
        # Log full request details
        logger.debug("Making API request with:")
        logger.debug(f"  URL: {BASE_URL}")
        logger.debug(f"  Method: GET")
        logger.debug(f"  Headers: {headers}")
        logger.debug(f"  Params: {params}")
        
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
    """Save the retrieved life logs to a JSON file."""
    if not data:
        logger.warning(f"No data to save for date {date}")
        return
    
    logger.info(f"Saving lifelogs data for date: {date}")
    
    try:
        # Create unique filename with timestamp to avoid overwrites
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SAVE_DIR, f'lifelogs_{date}_{timestamp}.json')
        
        logger.debug(f"Saving data to file: {filename}")
        logger.debug(f"Data type: {type(data)}")
        logger.debug(f"Data size (approx): {len(str(data))} characters")
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        file_size = os.path.getsize(filename)
        logger.info(f"Data saved successfully to {filename} ({file_size} bytes)")
        
    except Exception as e:
        logger.error(f"Error saving data for {date}: {e}")
        logger.error("Detailed traceback:", exc_info=True)

def initial_sync():
    """Perform the initial synchronization from March 1st to today."""
    logger.info("Starting initial Limitless data synchronization")
    
    today = datetime.now()
    start_date = INITIAL_SYNC_DATE
    
    logger.info(f"Today's date: {today.strftime('%Y-%m-%d')}")
    logger.info(f"Initial sync start date: {start_date.strftime('%Y-%m-%d')}")
    logger.info(f"Total date range: {(today - start_date).days} days")
    
    # Process one week at a time to avoid large API requests
    current_start = start_date
    period_count = 0
    success_count = 0
    
    while current_start <= today:
        period_count += 1
        current_end = min(current_start + timedelta(days=7), today)
        
        logger.info("-" * 60)
        logger.info(f"Processing period {period_count}: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
        
        try:
            data = fetch_lifelogs(current_start, current_end)
            if data:
                # Save with the end date of the period
                save_lifelogs(data, current_end.strftime('%Y-%m-%d'))
                logger.info(f"Successfully processed period {period_count}")
                success_count += 1
            else:
                logger.warning(f"No data was retrieved for period {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
                
        except Exception as e:
            logger.error(f"Unexpected error during synchronization for period {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}: {e}")
            logger.error("Detailed traceback:", exc_info=True)
        
        # Move to the next period
        current_start = current_end + timedelta(days=1)
        
        # Small delay between API calls to avoid rate limiting
        if current_start <= today:
            logger.debug("Waiting 1 second before next API call...")
            import time
            time.sleep(1)
    
    logger.info("-" * 60)
    logger.info(f"Initial synchronization completed. Processed {period_count} time periods with {success_count} successful downloads.")
    logger.info("=" * 80)

if __name__ == '__main__':
    try:
        # Check if API key is provided and valid
        if not API_KEY or API_KEY == 'YOUR_API_KEY':
            logger.error("No valid API key provided. Please provide your Limitless API key.")
            print("ERROR: No valid API key provided.")
            print("You can provide your API key in one of these ways:")
            print("1. Command line argument: python initial_sync.py YOUR_API_KEY")
            print("2. Environment variable: export LIMITLESS_API_KEY=YOUR_API_KEY")
            print("3. When prompted during script execution")
            sys.exit(1)
            
        initial_sync()
        
        print("=" * 60)
        print("Initial synchronization completed.")
        print(f"Check the log file for details: {LOG_FILE}")
        print("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        print("\nScript interrupted by user.")
    except Exception as e:
        logger.critical(f"Fatal error in initial sync program: {e}")
        logger.critical("Detailed error traceback:", exc_info=True)
        print(f"Fatal error: {e}")
        print(f"See log file for details: {LOG_FILE}")
        sys.exit(1)