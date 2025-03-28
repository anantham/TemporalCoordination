#!/usr/bin/env python3
"""
Telegram Saved Messages Fetcher and Updater (Pyrogram)

This script connects to Telegram's API using Pyrogram, checks for new messages
in your Saved Messages chat since the last update, and appends them to your
result.json file that stores your saved messages history.

Usage:
    1. Create a .env file with your API credentials (API_ID, API_HASH, and optionally SESSION_NAME).
    2. Run the script: python fetch_saved_messages.py
    3. On the first run, follow the authentication prompts (the session will be saved for subsequent runs).

Options:
    --monitor: Keep the script running to listen for new messages and update in real-time
    --backup: Create a backup of the existing JSON file before updating
"""

import os
import json
import logging
import datetime
import argparse
import time
import sys
import platform
from pathlib import Path
from datetime import datetime, timedelta
import shutil
import socket

# Import platform-specific modules
is_windows = platform.system() == "Windows"
if is_windows:
    import msvcrt
else:
    import fcntl
from dotenv import load_dotenv
from pyrogram import Client, filters, types
from pyrogram.errors import FloodWait, SessionPasswordNeeded, Unauthorized, SessionRevoked

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Telegram Saved Messages Updater")
    parser.add_argument("--monitor", action="store_true", 
                        help="Keep running to listen for new messages and update in real-time")
    parser.add_argument("--backup", action="store_true", 
                        help="Create a backup of the existing JSON file before updating")
    parser.add_argument("--json_file", type=str, default="result.json", 
                        help="Path to the result.json file (default: result.json)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Number of messages to fetch in each batch (default: 100)")
    parser.add_argument("--batch-delay", type=int, default=3,
                        help="Delay between batches in seconds to avoid rate limits (default: 3)")
    parser.add_argument("--polling-interval", type=int, default=300,
                        help="Polling interval in seconds for monitor mode (default: 300)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of worker threads for Pyrogram (default: 1, minimum: 1)")
    return parser.parse_args()

def format_message_for_json(message):
    """Convert a Pyrogram message object to the format used in the result.json file."""
    # Create the base message structure
    formatted_message = {
        "id": message.id,
        "type": "message",
        "date": message.date.strftime("%Y-%m-%dT%H:%M:%S"),
        "date_unixtime": str(int(message.date.timestamp())),
        "from": "Aditya",  # Assuming all saved messages are from the user
        "from_id": f"user{message.chat.id}",
        "text_entities": []
    }
    
    # Handle different message types
    if message.text:
        formatted_message["text"] = message.text
        formatted_message["text_entities"] = [{"type": "plain", "text": message.text}]
    elif message.caption:
        formatted_message["text"] = message.caption
        formatted_message["text_entities"] = [{"type": "plain", "text": message.caption}]
    elif message.photo:
        formatted_message["text"] = "[Photo]"
        formatted_message["text_entities"] = [{"type": "plain", "text": "[Photo]"}]
        # You could also handle media downloads here if needed
    elif message.document:
        formatted_message["text"] = f"[Document: {message.document.file_name}]"
        formatted_message["text_entities"] = [{"type": "plain", "text": f"[Document: {message.document.file_name}]"}]
    elif message.audio:
        formatted_message["text"] = f"[Audio: {message.audio.file_name if message.audio.file_name else 'Audio file'}]"
        formatted_message["text_entities"] = [{"type": "plain", "text": formatted_message["text"]}]
    elif message.video:
        formatted_message["text"] = "[Video]"
        formatted_message["text_entities"] = [{"type": "plain", "text": "[Video]"}]
    elif message.voice:
        formatted_message["text"] = "[Voice message]"
        formatted_message["text_entities"] = [{"type": "plain", "text": "[Voice message]"}]
    elif message.sticker:
        formatted_message["text"] = f"[Sticker: {message.sticker.emoji if message.sticker.emoji else 'Sticker'}]"
        formatted_message["text_entities"] = [{"type": "plain", "text": formatted_message["text"]}]
    else:
        formatted_message["text"] = "[Unsupported message type]"
        formatted_message["text_entities"] = [{"type": "plain", "text": "[Unsupported message type]"}]
    
    return formatted_message

def get_latest_message_date(json_data):
    """Extract the date of the most recent message in the JSON data."""
    if not json_data.get("messages"):
        return None
    
    try:
        # Find the maximum date in the messages
        latest_date = max(
            datetime.strptime(msg["date"], "%Y-%m-%dT%H:%M:%S") 
            for msg in json_data["messages"]
        )
        return latest_date
    except Exception as e:
        logger.error(f"Error finding latest message date: {e}")
        return None

def backup_json_file(json_file_path):
    """Create a backup of the JSON file with timestamp."""
    if not os.path.exists(json_file_path):
        logger.warning(f"No file to backup at {json_file_path}")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{json_file_path}.backup_{timestamp}"
    try:
        shutil.copy2(json_file_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")

def obtain_lock(lock_file):
    """Obtain a lock file to prevent multiple instances from running simultaneously."""
    # Different implementations for Windows and Unix
    if is_windows:
        try:
            # For Windows, we use a socket-based lock
            # Create a lock file and try to exclusively open it
            lock_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Use a lock file name as a unique port number (use hash to convert to an integer)
            port = hash(lock_file) % 10000 + 10000  # Generate port between 10000-20000
            try:
                lock_socket.bind(('localhost', port))
                # If we get here, the lock was obtained
                return lock_socket
            except socket.error:
                # Port is in use, another instance is running
                logger.error("Another instance is already running. Exiting.")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Error creating lock: {e}")
            sys.exit(1)
    else:
        # Unix-based systems use fcntl
        try:
            lock_file_handle = open(lock_file, 'w')
            fcntl.lockf(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_file_handle
        except IOError:
            logger.error("Another instance is already running. Exiting.")
            sys.exit(1)

def release_lock(lock_handle):
    """Release the lock file."""
    if lock_handle:
        if is_windows and isinstance(lock_handle, socket.socket):
            lock_handle.close()
        elif not is_windows:
            lock_handle.close()

def fetch_messages(app, json_data, latest_date, batch_size, batch_delay):
    """Fetch messages from Telegram and update json_data."""
    try:
        # Extract existing message IDs for redundancy checking
        existing_message_ids = set()
        for msg in json_data["messages"]:
            if "id" in msg:
                existing_message_ids.add(msg["id"])
        
        logger.info(f"Found {len(existing_message_ids)} existing message IDs in the JSON file")
        
        # Initialize variables for pagination
        all_messages = []
        total_fetched = 0
        pagination_offset = 0
        more_messages = True
        oldest_date = datetime.fromtimestamp(int(latest_date.timestamp()) + 1) if latest_date else None
        consecutive_duplicates = 0  # Track consecutive duplicates to detect when we're done
        max_consecutive_duplicates = 5  # Stop after this many consecutive duplicates
        
        logger.info(f"Fetching messages in batches of {batch_size} with {batch_delay}s delay between batches")
        
        # Fetch in batches with pagination to respect API limits
        while more_messages:
            try:
                # Fetch next batch of messages
                if oldest_date:
                    logger.info(f"Fetching batch from offset {pagination_offset} after {oldest_date}")
                    batch = list(app.get_chat_history("me", limit=batch_size, offset=pagination_offset, offset_date=oldest_date))
                else:
                    logger.info(f"Fetching batch from offset {pagination_offset} (full history)")
                    batch = list(app.get_chat_history("me", limit=batch_size, offset=pagination_offset))
                
                # If no more messages or empty batch, we're done
                if not batch:
                    logger.info(f"No more messages found after offset {pagination_offset}")
                    more_messages = False
                    break
                
                logger.info(f"Fetched {len(batch)} messages in this batch")
                
                # Check for duplicates in this batch
                new_in_batch = 0
                duplicate_in_batch = 0
                
                for message in batch:
                    if message.id in existing_message_ids:
                        duplicate_in_batch += 1
                        consecutive_duplicates += 1
                    else:
                        new_in_batch += 1
                        consecutive_duplicates = 0  # Reset counter when we find a new message
                        all_messages.append(message)
                        existing_message_ids.add(message.id)  # Add to set to prevent future dupes
                
                logger.info(f"Batch contains {new_in_batch} new messages and {duplicate_in_batch} duplicates")
                
                # If we found mostly/all duplicates, we might be done
                if consecutive_duplicates >= max_consecutive_duplicates:
                    logger.info(f"Found {consecutive_duplicates} consecutive duplicates, stopping fetch")
                    more_messages = False
                    break
                    
                # If the batch was all duplicates, we're likely reaching overlap with existing data
                if duplicate_in_batch == len(batch):
                    logger.info("Entire batch contains duplicates, likely reached overlap with existing data")
                    more_messages = False
                    break
                    
                total_fetched += new_in_batch
                
                # Update pagination offset for next batch
                pagination_offset += len(batch)
                
                # If we got fewer messages than the batch size, we're likely at the end
                if len(batch) < batch_size:
                    logger.info(f"Received fewer messages than batch size, likely reached the end")
                    more_messages = False
                
                # Add a delay before the next batch to avoid rate limits
                # Skip the delay for the last batch
                if more_messages:
                    logger.info(f"Waiting {batch_delay}s before fetching next batch...")
                    time.sleep(batch_delay)
                    
            except FloodWait as e:
                # Handle rate limiting with exponential backoff
                wait_time = e.value
                logger.warning(f"Hit rate limit, must wait {wait_time} seconds before next request")
                time.sleep(wait_time)
                # Continue without updating offset (retry the same batch)
                continue
            
        logger.info(f"Fetched a total of {total_fetched} new messages across {pagination_offset // batch_size + 1} batches")
        
        # Sort messages by date (oldest first to maintain chronological order)
        all_messages.sort(key=lambda x: x.date)
        
        # Process and add each new message
        if all_messages:
            new_messages_count = 0
            # Process messages one by one
            for message in all_messages:
                # Double-check we don't already have this message ID (belt and suspenders)
                message_id = message.id
                if any(msg.get("id") == message_id for msg in json_data["messages"]):
                    logger.debug(f"Skipping message {message_id} (already exists in JSON)")
                    continue
                    
                # Skip messages that are older than our latest message (safety check)
                if latest_date and message.date <= latest_date:
                    logger.debug(f"Skipping message from {message.date} (older than our latest message)")
                    continue
                
                # Format and add the message
                formatted_message = format_message_for_json(message)
                json_data["messages"].append(formatted_message)
                new_messages_count += 1
            
            # Update the JSON file only if we have new messages
            if new_messages_count > 0:
                logger.info(f"Adding {new_messages_count} new messages to JSON")
                
                # Make sure the ID is updated if needed
                if json_data["messages"] and "from_id" in json_data["messages"][0]:
                    user_id = json_data["messages"][0]["from_id"].replace("user", "")
                    json_data["id"] = int(user_id)
                
                # Return the updated json_data
                return json_data, True
            else:
                logger.info("No new messages to add.")
                return json_data, False
        else:
            logger.info("No messages retrieved from Telegram.")
            return json_data, False
            
    except Exception as e:
        logger.error(f"Error fetching or processing messages: {e}")
        return json_data, False

def save_json_data(json_data, json_file_path):
    """Save the JSON data to file."""
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=1, ensure_ascii=False)
        logger.info(f"Successfully updated {json_file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving updated JSON: {e}")
        return False

def monitor_for_messages(app, json_data, json_file_path, args):
    """Run the monitoring loop to continuously poll for new messages."""
    logger.info(f"Monitoring for new messages. Checking every {args.polling_interval} seconds. Press Ctrl+C to exit.")
    
    try:
        # More conservative polling parameters with exponential backoff
        polling_interval = max(args.polling_interval, 300)  # At least 5 minutes
        max_polling_interval = 1800  # 30 minutes max
        backoff_factor = 1.5
        last_check_time = datetime.now()
        
        while True:
            try:
                # Wait for the polling interval
                logger.info(f"Waiting {polling_interval} seconds before next check...")
                time.sleep(polling_interval)
                
                current_time = datetime.now()
                logger.info(f"Checking for new messages since {last_check_time}")
                
                # Reconnect for each poll to ensure a fresh state
                # This helps avoid the SESSION_REVOKED error
                with app:
                    # Get only messages since the last check
                    new_messages = list(app.get_chat_history(
                        "me", 
                        limit=50,  # Reasonable limit for new messages in a polling interval
                        offset_date=last_check_time
                    ))
                    
                    if new_messages:
                        logger.info(f"Found {len(new_messages)} new messages during poll")
                        
                        # Process only messages we don't already have
                        added_count = 0
                        for message in sorted(new_messages, key=lambda x: x.date):
                            # Skip if we already have a message with this ID
                            message_ids = [msg.get("id") for msg in json_data["messages"]]
                            if message.id in message_ids:
                                continue
                            
                            # Format and add the message
                            formatted_message = format_message_for_json(message)
                            json_data["messages"].append(formatted_message)
                            added_count += 1
                        
                        # Save if we added messages
                        if added_count > 0:
                            logger.info(f"Added {added_count} new messages from polling")
                            save_json_data(json_data, json_file_path)
                    else:
                        logger.info("No new messages found during this poll")
                
                # Update the last check time
                last_check_time = current_time
                
                # Adaptive polling with more conservative parameters
                if not new_messages and polling_interval < max_polling_interval:
                    polling_interval = min(polling_interval * backoff_factor, max_polling_interval)
                    logger.info(f"No new messages, increasing polling interval to {polling_interval:.1f}s")
                elif new_messages and polling_interval > args.polling_interval:
                    # If we found messages, decrease interval back toward the original
                    polling_interval = max(args.polling_interval, polling_interval / backoff_factor)
                    logger.info(f"Found messages, decreasing polling interval to {polling_interval:.1f}s")
                
            except FloodWait as e:
                wait_time = e.value
                logger.warning(f"Rate limited during polling, waiting {wait_time}s")
                time.sleep(wait_time)
                # Increase polling interval after a flood wait
                polling_interval = min(polling_interval * 2, max_polling_interval)
                logger.info(f"Increasing polling interval to {polling_interval:.1f}s after rate limit")
            
            except SessionRevoked as e:
                logger.error(f"Session revoked during polling: {e}")
                logger.info("Removing session file and exiting monitor mode")
                raise  # Re-raise to be handled by the outer try block
                
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            
            except Exception as e:
                logger.error(f"Error during polling: {e}")
                # Add a longer delay after errors and increase backoff
                time.sleep(60)
                polling_interval = min(polling_interval * 2, max_polling_interval)
        
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted by user")
    except SessionRevoked:
        # Let the main function handle this exception
        raise

def main():
    # Parse command line arguments
    args = parse_args()
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Retrieve credentials from the environment
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_name = os.getenv("SESSION_NAME", "my_pyrogram_session")
    
    if not api_id or not api_hash:
        logger.error("API_ID and API_HASH must be set in the .env file.")
        return
        
    # Obtain lock to prevent multiple instances
    lock_file = f"{session_name}.lock"
    lock_handle = None
    
    try:
        lock_handle = obtain_lock(lock_file)
        
        # Json file path
        json_file_path = Path(args.json_file)
        
        # Create a backup if requested
        if args.backup and json_file_path.exists():
            backup_json_file(json_file_path)
        
        # Load existing JSON data if the file exists
        if json_file_path.exists():
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    logger.info(f"Loaded existing data from {json_file_path}")
            except Exception as e:
                logger.error(f"Error loading JSON file: {e}")
                logger.info("Creating a new JSON structure")
                json_data = {"type": "saved_messages", "id": 0, "messages": []}
        else:
            logger.info(f"JSON file not found. Creating a new structure.")
            json_data = {"type": "saved_messages", "id": 0, "messages": []}
        
        # Get the latest message date from the JSON
        latest_date = get_latest_message_date(json_data)
        if latest_date:
            logger.info(f"Latest message in JSON is from: {latest_date}")
        else:
            logger.info("No existing messages found in the JSON file")
        
        # Create a Pyrogram client instance with minimal workers to avoid triggering session termination
        workers = max(1, args.workers)  # Ensure at least 1 worker (Pyrogram requirement)
        
        logger.info(f"Initializing Pyrogram client with {workers} worker{'s' if workers != 1 else ''}")
        app = Client(
            session_name, 
            api_id=int(api_id), 
            api_hash=api_hash,
            workers=workers,  # Minimal workers to avoid Telegram security triggers
            no_updates=True  # Always disable updates, we'll handle them manually
        )
        
        try:
            # Connect and fetch messages
            with app:
                logger.info("Connected to Telegram successfully.")
                updated_json_data, changes_made = fetch_messages(
                    app, json_data, latest_date, args.batch_size, args.batch_delay
                )
                
                if changes_made:
                    save_json_data(updated_json_data, json_file_path)
                    json_data = updated_json_data  # Update reference for monitor mode
            
            # If monitoring is enabled, start the monitoring loop
            if args.monitor:
                monitor_for_messages(app, json_data, json_file_path, args)
            else:
                logger.info("Finished updating saved messages JSON.")
                
        except SessionRevoked:
            logger.error("Session was revoked by Telegram. Removing session file and exiting.")
            # Remove the session file to start fresh next time
            session_path = Path(f"{session_name}.session")
            if session_path.exists():
                session_path.unlink()
            logger.info("Please run the script again to reauthorize.")
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Always release the lock when done
        if lock_handle:
            release_lock(lock_handle)
            
    logger.info("Script completed.")

if __name__ == "__main__":
    main()