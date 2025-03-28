#!/usr/bin/env python3
"""
Telegram Prayer CSV - Identifies prayer patterns in messages using Ollama and saves to CSV
No pandas dependency - pure Python implementation
"""

import json
import os
import sys
import csv
from datetime import datetime
import requests
import time
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

# =============================================================================
# CONFIGURATION - Edit these values to change defaults
# =============================================================================

# Default model to use (change this single variable to switch models)
DEFAULT_MODEL = "gemma3:12b"  # Options: "llama3.2:latest", "gemma3:27b", "qwq:latest", "deepseek-r1:32b", "phi4:latest", "olmo2:13b"

# Model timeouts in seconds
MODEL_TIMEOUTS = {
    "llama3.2:latest": 30,    # Smaller model, needs less time
    "gemma3:27b": 120,        # Large model, needs more time
    "qwq:latest": 120,        # Large model, needs more time
    "deepseek-r1:32b": 120,   # Large model, needs more time
    "phi4:latest": 60,        # Medium model
    "olmo2:13b": 60           # Medium model
}

# =============================================================================
# End of configuration
# =============================================================================

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("prayer_csv.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PrayerCSV")

class TelegramPrayerCSV:
    def __init__(self, file_path: str, prayer_context_path: str, 
                 # Model is now controlled by DEFAULT_MODEL at top of file
                 model: str = DEFAULT_MODEL,
                 context_before: int = 3, context_after: int = 2, smart_context: bool = False,
                 max_context_before: int = 10, max_context_after: int = 10,
                 base_timeout: int = 60, verbose: bool = False, context_method: str = "llm"):
        # Use the global model timeout mapping
        self.model_timeouts = MODEL_TIMEOUTS
        self.file_path = file_path
        self.prayer_context_path = prayer_context_path
        self.model = model
        self.data = None
        self.messages = []
        self.prayer_context = ""
        self.output_dir = os.path.dirname(file_path)
        self.existing_results = {}  # Will store message_id -> prayer mappings for already processed messages
        self.context_before = context_before  # Number of messages before target to include as context
        self.context_after = context_after    # Number of messages after target to include as context
        self.smart_context = smart_context    # Whether to use dynamic context selection
        self.max_context_before = max_context_before  # Maximum messages to consider before (for smart context)
        self.max_context_after = max_context_after    # Maximum messages to consider after (for smart context)
        self.base_timeout = base_timeout      # Base timeout value
        self.verbose = verbose                # Whether to enable verbose logging
        self.context_method = context_method  # Method for smart context: "llm", "time", or "hybrid"
        
        # Set appropriate timeout based on model
        self.timeout = self.model_timeouts.get(self.model, base_timeout)
        logger.info(f"Using timeout of {self.timeout}s for model {self.model}")
        
    def load_data(self) -> bool:
        """Load the JSON messages data and prayer context"""
        try:
            logger.info(f"Loading data from {self.file_path}...")
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
                
            if 'messages' in self.data:
                self.messages = self.data['messages']
                logger.info(f"Loaded {len(self.messages)} messages.")
            else:
                logger.error("No 'messages' field found in the JSON")
                return False
            
            # Load prayer context
            try:
                with open(self.prayer_context_path, 'r', encoding='utf-8') as f:
                    self.prayer_context = f.read()
                logger.info(f"Loaded prayer context: {len(self.prayer_context)} chars")
            except Exception as e:
                logger.error(f"Error loading prayer context: {e}")
                return False
                
            return True
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False
    
    def extract_text(self, message: Dict[str, Any]) -> str:
        """Extract text from a message, handling various formats"""
        text = message.get('text', '')
        
        # Handle text as list of entities
        if isinstance(text, list):
            extracted_text = []
            for item in text:
                if isinstance(item, str):
                    extracted_text.append(item)
                elif isinstance(item, dict) and 'text' in item:
                    extracted_text.append(item['text'])
            text = ''.join(extracted_text)
        
        # Handle text entities separately if present
        elif 'text_entities' in message:
            entities = message['text_entities']
            if isinstance(entities, list):
                extracted_text = []
                for entity in entities:
                    if isinstance(entity, dict) and 'text' in entity:
                        extracted_text.append(entity['text'])
                # If we got entities but text was empty, use the extracted text
                if not text and extracted_text:
                    text = ''.join(extracted_text)
        
        # Clean text for CSV
        # Remove newlines and replace with space
        text = text.replace('\n', ' ').replace('\r', ' ')
        # Ensure no double quotes break the CSV
        text = text.replace('"', '""')
        
        return text
        
    def get_message_with_context(self, messages: List[Dict[str, Any]], current_index: int) -> Tuple[str, str]:
        """Get a message with its surrounding context messages
        
        Returns:
            Tuple of (target_message_text, context_string)
        """
        if not messages or current_index < 0 or current_index >= len(messages):
            return "", ""
            
        # Get the target message
        target_message = messages[current_index]
        target_text = self.extract_text(target_message)
        if not target_text:
            return "", ""
        
        if self.smart_context:
            return self.get_smart_context(messages, current_index, target_text)
        else:
            # Fixed context window approach
            # Calculate context window boundaries
            start_idx = max(0, current_index - self.context_before)
            end_idx = min(len(messages) - 1, current_index + self.context_after)
            
            # Collect context messages
            context_messages = []
            for i in range(start_idx, end_idx + 1):
                if i == current_index:  # Skip the target message in context collection
                    continue
                    
                msg = messages[i]
                text = self.extract_text(msg)
                if text:
                    # Get timestamp
                    try:
                        timestamp = datetime.strptime(msg['date'], "%Y-%m-%dT%H:%M:%S")
                        time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, KeyError):
                        time_str = "Unknown time"
                        
                    # Add position indicator (before/after)
                    position = "BEFORE" if i < current_index else "AFTER"
                    sender = msg.get('from', 'Unknown')
                    
                    # Format the context message
                    context_messages.append(f"[{position} - {time_str} - {sender}]: {text}")
            
            # Combine into context string
            context_string = "\n".join(context_messages)
            
            return target_text, context_string
            
    def get_smart_context(self, messages: List[Dict[str, Any]], current_index: int, target_text: str) -> Tuple[str, str]:
        """Get dynamically selected relevant context for a message
        
        Args:
            messages: List of message dictionaries
            current_index: Index of the target message
            target_text: Text of the target message
            
        Returns:
            Tuple of (target_message_text, context_string)
        """
        # Use the context method specified in __init__
        if self.context_method == "time":
            return self.get_time_based_context(messages, current_index, target_text)
        elif self.context_method == "hybrid":
            # First try time-based, but if not enough context found, fall back to LLM
            target, context = self.get_time_based_context(messages, current_index, target_text)
            if not context:
                return self.get_llm_based_context(messages, current_index, target_text)
            return target, context
        else:  # default to LLM-based
            return self.get_llm_based_context(messages, current_index, target_text)
    
    def get_time_based_context(self, messages: List[Dict[str, Any]], current_index: int, target_text: str) -> Tuple[str, str]:
        """Get dynamically selected relevant context for a message using time-based heuristics
        
        Args:
            messages: List of message dictionaries
            current_index: Index of the target message
            target_text: Text of the target message
            
        Returns:
            Tuple of (target_message_text, context_string)
        """
        if not messages or current_index < 0 or current_index >= len(messages):
            return target_text, ""
            
        # Get target message timestamp
        target_msg = messages[current_index]
        try:
            target_timestamp = datetime.strptime(target_msg['date'], "%Y-%m-%dT%H:%M:%S")
        except (ValueError, KeyError):
            # If we can't parse the timestamp, fall back to fixed context
            logger.warning("Could not parse target message timestamp. Falling back to fixed context.")
            return self.get_message_with_context(messages, current_index)
        
        # Define time thresholds - much tighter than before
        TIME_THRESHOLD_MINUTES = 10  # Only include messages within 10 minutes
        
        # Get a much wider context window for potential analysis (100 messages in each direction)
        start_idx = max(0, current_index - 100)
        end_idx = min(len(messages) - 1, current_index + 100)
        
        # Collect potential context messages with their relevance scores
        context_candidates = []
        
        for i in range(start_idx, end_idx + 1):
            if i == current_index:  # Skip the target message
                continue
                
            msg = messages[i]
            text = self.extract_text(msg)
            if not text:
                continue
                
            # Get message timestamp
            try:
                msg_timestamp = datetime.strptime(msg['date'], "%Y-%m-%dT%H:%M:%S")
                time_str = msg_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, KeyError):
                continue
            
            # Calculate time difference in minutes
            time_diff = abs((target_timestamp - msg_timestamp).total_seconds() / 60)
            
            # Only consider messages within the time threshold
            if time_diff <= TIME_THRESHOLD_MINUTES:
                # Score is inversely proportional to time difference
                # Messages closer in time get higher scores
                relevance_score = 100 - (time_diff * 9)  # 0 mins = 100, 10 mins = 10
                
                # Adjust score based on position (before/after)
                position = "BEFORE" if i < current_index else "AFTER"
                # Slightly prefer messages before the target
                if position == "BEFORE":
                    relevance_score *= 1.2
                
                # Score bonus for same sender as target message
                if msg.get('from') == target_msg.get('from'):
                    relevance_score *= 1.2  # Increased bonus for same sender
                
                # Prepare context message
                sender = msg.get('from', 'Unknown')
                context_msg = f"[{position} - {time_str} - {sender}]: {text}"
                
                # Add to candidates with score
                context_candidates.append((context_msg, relevance_score, i))
        
        # Sort by relevance score (descending)
        context_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # VERBOSE: Log what we're doing
        if self.verbose:
            logger.info(f"SELECTING TIME-BASED SMART CONTEXT FOR: {target_text[:100]}..." if len(target_text) > 100 else f"SELECTING TIME-BASED SMART CONTEXT FOR: {target_text}")
            logger.info(f"AVAILABLE MESSAGES: {len(context_candidates)}")
            # Log top 5 candidates with scores
            for i, (msg, score, idx) in enumerate(context_candidates[:5]):
                logger.info(f"Candidate {i+1}: Score {score:.1f} - {msg[:80]}...")
        
        # Include all messages within the time threshold, but cap at 10 messages
        MAX_CONTEXT_COUNT = 10
        
        selected_context = []
        indices = []
        
        for context_msg, score, idx in context_candidates[:MAX_CONTEXT_COUNT]:
            selected_context.append(context_msg)
            indices.append(idx - start_idx)  # Convert to local index
        
        # Join the selected context
        context_string = "\n".join(selected_context)
        
        if selected_context:
            logger.info(f"Time-based smart context selected {len(selected_context)} messages: {indices}")
            logger.info(f"All messages are within {TIME_THRESHOLD_MINUTES} minutes of target message")
        else:
            logger.info(f"No messages found within {TIME_THRESHOLD_MINUTES} minutes of target: {target_text[:30]}...")
        
        return target_text, context_string
        
    def get_llm_based_context(self, messages: List[Dict[str, Any]], current_index: int, target_text: str) -> Tuple[str, str]:
        """Get dynamically selected relevant context for a message using the LLM
        
        Args:
            messages: List of message dictionaries
            current_index: Index of the target message
            target_text: Text of the target message
            
        Returns:
            Tuple of (target_message_text, context_string)
        """
        # Get a wider context window for analysis
        start_idx = max(0, current_index - self.max_context_before)
        end_idx = min(len(messages) - 1, current_index + self.max_context_after)
        
        # Collect all potential context messages
        potential_context_msgs = []
        message_indices = []  # Keep track of original indices
        
        for i in range(start_idx, end_idx + 1):
            if i == current_index:  # Skip the target message
                continue
                
            msg = messages[i]
            text = self.extract_text(msg)
            if text:
                # Get timestamp
                try:
                    timestamp = datetime.strptime(msg['date'], "%Y-%m-%dT%H:%M:%S")
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, KeyError):
                    time_str = "Unknown time"
                    
                # Add position indicator (before/after)
                position = "BEFORE" if i < current_index else "AFTER"
                sender = msg.get('from', 'Unknown')
                
                # Format the context message with an index
                idx = len(potential_context_msgs)
                context_msg = f"[{idx}] [{position} - {time_str} - {sender}]: {text}"
                potential_context_msgs.append(context_msg)
                message_indices.append(i)  # Store original message index
        
        # VERBOSE: Log detailed information about the context selection process
        if self.verbose:
            logger.info(f"\n{'='*50}")
            logger.info(f"SELECTING LLM-BASED SMART CONTEXT FOR: {target_text[:100]}..." if len(target_text) > 100 else f"SELECTING LLM-BASED SMART CONTEXT FOR: {target_text}")
            logger.info(f"AVAILABLE MESSAGES: {len(potential_context_msgs)}")
            logger.info(f"CONTEXT WINDOW: {start_idx} to {end_idx} (using max_before={self.max_context_before}, max_after={self.max_context_after})")
            
            # Show sample of available messages for debugging
            logger.info(f"SAMPLE MESSAGES BEING SENT TO LLM:")
            for i, msg in enumerate(potential_context_msgs[:5]):  # Show first 5 messages
                logger.info(f"  Message {i}: {msg[:150]}..." if len(msg) > 150 else f"  Message {i}: {msg}")
            if len(potential_context_msgs) > 5:
                logger.info(f"  ... and {len(potential_context_msgs)-5} more messages")
            logger.info(f"{'='*50}")
        
        if not potential_context_msgs:
            return target_text, ""  # No potential context available
            
        # Now use the LLM to determine which messages are relevant context
        prompt = f"""
You are helping to determine which messages provide relevant context for understanding whether a message contains a prayer or wish pattern based on a specific Prayer Wishlist definition.

### Prayer Wishlist Definition:
{self.prayer_context}

### Target Message:
"{target_text}"

### Available Context Messages:
{chr(10).join(potential_context_msgs)}

### Instructions:
1. Analyze the target message in light of the Prayer Wishlist definition above.
2. Determine which of the context messages (if any) would help understand if the target message contains one of the specific prayer patterns defined in the Prayer Wishlist.
3. Only select messages that:
   - Are part of the same conversation thread/topic
   - Help clarify the intent or meaning of the target message
   - Provide clues about which prayer pattern (if any) is being invoked
4. Many messages may be completely irrelevant - be selective!
5. Respond with ONLY a comma-separated list of the indices of relevant messages. For example: "0,3,5" or "none" if no messages are relevant.

Relevant message indices (comma-separated):
"""
        
        # Call Ollama API to get relevant indices
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                logger.warning(f"Smart context selection failed: {response.status_code}. Falling back to fixed context.")
                # Fall back to fixed context
                return self.get_message_with_context(messages, current_index)
            
            # Parse the response to get relevant indices
            result = response.json()
            indices_text = result.get('response', '').strip()
            
            # VERBOSE: Log detailed information about the response
            if self.verbose:
                logger.info(f"RAW CONTEXT SELECTION RESPONSE: {indices_text}")
                # Log the full response object for debugging
                logger.info(f"RESPONSE DETAILS:")
                for key, value in result.items():
                    if key != 'response':  # Skip the response text as we already logged it
                        logger.info(f"  {key}: {value}")
                logger.info(f"{'='*50}")
                
            # Extract from thinking tags if present - IMPORTANT
            thinking_match = re.search(r'<think>(.*?)</think>\s*(.*)', indices_text, re.DOTALL)
            if thinking_match:
                # Get just the content after the thinking tags
                indices_text = thinking_match.group(2).strip()
                if self.verbose:
                    logger.info(f"EXTRACTED FROM THINKING TAGS: {indices_text}")
            
            # Handle "none" or empty response first, before any regex processing
            if indices_text.lower().strip() in ('none', 'no relevant messages', 'no') or not indices_text.strip():
                logger.info(f"Smart context found no relevant messages for target: {target_text[:30]}...")
                return target_text, ""
            
            # Check if the response is mostly text rather than indices
            # If the model returned a verbose explanation instead of numbers
            if len(indices_text.split()) > 5 and not re.match(r'^[\d,\s]+$', indices_text.strip()):
                logger.info(f"Model returned text instead of indices: {indices_text[:50]}...")
                return target_text, ""
                
            # Parse comma-separated indices
            try:
                # Handle various formats the model might return
                # Only apply regex if the text looks like it contains indices
                if re.search(r'\d+', indices_text):
                    indices_text = re.sub(r'[^\d,]', '', indices_text)  # Keep only digits and commas
                else:
                    return target_text, ""
                    
                if not indices_text:
                    return target_text, ""
                    
                relevant_indices = [int(idx.strip()) for idx in indices_text.split(',') if idx.strip()]
                # Filter out invalid indices
                relevant_indices = [idx for idx in relevant_indices if 0 <= idx < len(potential_context_msgs)]
                
                if not relevant_indices:
                    logger.info(f"No valid relevant indices found in response: {indices_text}")
                    return target_text, ""
                
                # Collect relevant context messages
                selected_context = []
                for idx in relevant_indices:
                    selected_context.append(potential_context_msgs[idx])
                
                # Join the selected context
                context_string = "\n".join(selected_context)
                logger.info(f"LLM-based smart context selected {len(relevant_indices)} messages: {relevant_indices}")
                
                return target_text, context_string
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing relevant indices '{indices_text}': {e}. Falling back to fixed context.")
                # Fall back to fixed context
                return self.get_message_with_context(messages, current_index)
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Smart context request failed: {e}. Falling back to fixed context.")
            # Fall back to fixed context window
            return self.get_message_with_context(messages, current_index)
    
    def analyze_prayer_with_ollama(self, message_text: str, context_text: str = "", max_retries: int = 3, retry_delay: float = 2.0) -> str:
        """Send a message to Ollama to identify prayer patterns with retries for robustness"""
        if not message_text.strip():
            return "No"  # Empty message, no prayer
        
        # VERBOSE: Log only the message being analyzed, not the whole prompt
        if self.verbose:
            logger.info(f"\n{'='*50}")
            logger.info(f"ANALYZING MESSAGE: {message_text[:100]}..." if len(message_text) > 100 else f"ANALYZING MESSAGE: {message_text}")
            if context_text:
                # Show just a preview of context if it exists
                context_preview = context_text[:150] + "..." if len(context_text) > 150 else context_text
                logger.info(f"WITH CONTEXT: {context_preview}")
            logger.info(f"{'='*50}")
        
        # Include context section if provided
        context_section = ""
        if context_text:
            context_section = f"""
### Surrounding Message Context:
{context_text}
"""
            
        # Prepare the prompt with the prayer context
        prompt = f"""
### Context on Prayer Wishlist
{self.prayer_context}
{context_section}

### Instructions:
Analyze the message above and identify if any of the prayers from the Prayer Wishlist are detected.
- If no prayer is detected, respond with only: "No"
- If a prayer is detected, that is ONLY if there is the character p (by itself not in a word) is found somewhere in the message, then respond with the corresponding output format as described in the Context on Prayer Wishlist 

Remember ONLY a single prayer is to be detected for any message and ignore if the prayer is found in the context messages, we only care if the prayer is to be found in the message to analyze. The context messages are useful to populate the arguments in the response list.

Let's look at some examples

Message 1 to analyze is,
P project - A writes a doc and B writes comments and A refers to comments and updates doc and resolves comments and asks B to give more feedback on new version, A would like to pull up old comments, on old sections of old draft and then have the AI show the diff to which part of the new doc it corresponds to

Appropriate response 2 is,
[Project, A writes a doc and B writes comments and A refers to comments and updates doc and resolves comments and asks B to give more feedback on new version, A would like to pull up old comments, on old sections of old draft and then have the AI show the diff to which part of the new doc it corresponds to]


Message 2 to analyze is,
P remind to buy btc and eth on next dip

Appropriate response 2 is,
[Remind, next dip of BTC and ETH, readjust portfolio by accumulating more ETH and BTC]

Message 3 to analyze is,
P recommend Frank Ocean music by Thapa BMC

Appropriate response 3 is,
[Recommend, Songs by Frank Ocean, Thapa from BMC]

Message 4 to analyze is,
p send to sid hey man when shall we talk

Appropriate response 3 is,
[SendTo, Sid, hey man when shall we talk]


### Message to analyze:
"{message_text}"


You may use CoT reasoning tokens but make sure to end your response with Output format - <final answer>


Prayer detection for this new message:

"""
        
        # Implement retry logic
        retries = 0
        while retries <= max_retries:
            try:
                # Call Ollama API with increasing timeout for retries
                # Base timeout from model size plus retry extension
                timeout = self.timeout + (retries * 30)  # Add 30 seconds per retry
                
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Low temperature for more precise answers
                            "top_p": 0.9
                        }
                    },
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    raw_answer = result.get('response', 'Error: No response').strip()
                    
                    # VERBOSE: Log the raw answer
                    if self.verbose:
                        logger.info(f"RAW MODEL RESPONSE: {raw_answer}")
                        logger.info(f"{'='*50}")
                    
                    # Extract from thinking tags if present
                    thinking_match = re.search(r'<think>(.*?)</think>\s*(.*?)$', raw_answer, re.DOTALL)
                    if thinking_match:
                        # Get just the content after the thinking tags
                        raw_answer = thinking_match.group(2).strip()
                        if self.verbose:
                            logger.info(f"EXTRACTED FROM THINKING TAGS: {raw_answer}")
                    
                    # Enhanced normalization of "No" answers
                    if (raw_answer.lower() in ('no', 'none', 'no prayer detected') or
                        'does not contain' in raw_answer.lower() or
                        'no prayer is detected' in raw_answer.lower() or
                        'not contain any' in raw_answer.lower() or
                        'output format - no' in raw_answer.lower() or
                        'final answer\n\nno' in raw_answer.lower() or
                        'output format: no' in raw_answer.lower() or
                        'no specific prayer' in raw_answer.lower() or
                        'no prayer was found' in raw_answer.lower() or
                        'therefore, no prayer' in raw_answer.lower()):
                        if self.verbose:
                            logger.info(f"Normalized verbose NO response: {raw_answer[:50]}...")
                        return "No"
                    
                    # Extract prayers from brackets
                    bracket_match = re.search(r'\[(.*?)\]', raw_answer)
                    if bracket_match:
                        # Return just the bracketed content
                        answer = f"[{bracket_match.group(1)}]"
                        if self.verbose:
                            logger.info(f"EXTRACTED BRACKET: {answer}")
                            logger.info(f"{'='*50}")
                        return answer
                    
                    # If we get here and the answer is just a few words, it's probably "No"
                    if len(raw_answer.split()) <= 3:
                        if self.verbose:
                            logger.info(f"SHORT ANSWER TREATED AS NO: {raw_answer}")
                            logger.info(f"{'='*50}")
                        return "No"
                    
                    # Clean up common patterns in responses as fallback
                    answer = re.sub(r'I detected a |This appears to be a |Prayer detected: ', '', raw_answer, flags=re.IGNORECASE)
                    
                    # VERBOSE: Log the processed answer if different from raw
                    if self.verbose and answer != raw_answer:
                        logger.info(f"PROCESSED TO: {answer}")
                        logger.info(f"{'='*50}")
                    
                    return answer
                else:
                    # Log error and retry
                    logger.warning(f"Ollama API error on attempt {retries+1}/{max_retries+1}: {response.status_code} - {response.text}")
                    
                    if retries == max_retries:
                        logger.error(f"Giving up after {max_retries+1} attempts: API returned {response.status_code}")
                        return "Error: API request failed after retries"
                        
                    # Exponential backoff delay
                    sleep_time = retry_delay * (2 ** retries)
                    logger.info(f"Retrying in {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)
                    retries += 1
                    
            except requests.exceptions.RequestException as e:
                # Log error and retry for connection issues
                logger.warning(f"Ollama request failed on attempt {retries+1}/{max_retries+1}: {e}")
                
                if retries == max_retries:
                    logger.error(f"Giving up after {max_retries+1} attempts: {e}")
                    return "Error: Connection failed after retries"
                    
                # Exponential backoff delay
                sleep_time = retry_delay * (2 ** retries)
                logger.info(f"Retrying in {sleep_time:.1f} seconds...")
                time.sleep(sleep_time)
                retries += 1
                
        # This should not be reached, but just in case
        return "Error: Unexpected failure in retry logic"
    
    def process_messages(self, max_messages: int = -1) -> List[Dict[str, Any]]:
        """Process messages and analyze them for prayers"""
        if not self.messages:
            logger.warning("No messages available")
            return []
        
        # Prepare data for CSV
        processed_data = []
        
        # Sort messages by date
        sorted_messages = sorted(
            [msg for msg in self.messages if 'date' in msg],
            key=lambda x: datetime.strptime(x['date'], "%Y-%m-%dT%H:%M:%S"),
            reverse=True  # Most recent first
        )
        
        # Limit message count if specified
        if max_messages > 0:
            messages_to_process = sorted_messages[:max_messages]
            logger.info(f"Processing {len(messages_to_process)} of {len(sorted_messages)} messages")
        else:
            messages_to_process = sorted_messages
            logger.info(f"Processing all {len(messages_to_process)} messages")
        
        # Track prayer statistics
        prayer_counts = {"No": 0}
        
        # Process messages
        for i, msg in enumerate(messages_to_process):
            # Skip messages without date
            if 'date' not in msg:
                continue
                
            # Extract timestamp
            try:
                date_str = msg['date']
                timestamp = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
                
            # Get message ID
            message_id = msg.get('id')
            
            # Get message text with surrounding context
            current_msg_index = messages_to_process.index(msg)
            target_text, context_text = self.get_message_with_context(messages_to_process, current_msg_index)
            
            # Skip empty messages
            if not target_text:
                logger.debug(f"Skipping empty message {i+1}/{len(messages_to_process)}")
                continue
                
            # Check if we already have results for this message
            prayer_result = None
            if message_id in self.existing_results:
                prayer_result = self.existing_results[message_id]
                logger.info(f"Using existing result for message {i+1}/{len(messages_to_process)} from {timestamp}: {prayer_result}")
            else:
                # Analyze prayer with Ollama
                context_info = f" (with {self.context_before} before, {self.context_after} after)" if context_text else ""
                logger.info(f"Analyzing message {i+1}/{len(messages_to_process)} from {timestamp}{context_info}")
                prayer_result = self.analyze_prayer_with_ollama(target_text, context_text)
            
            # Update prayer statistics
            if prayer_result == "No":
                prayer_counts["No"] = prayer_counts.get("No", 0) + 1
            else:
                prayer_type = prayer_result.split(',')[0] if ',' in prayer_result else prayer_result
                prayer_counts[prayer_type] = prayer_counts.get(prayer_type, 0) + 1
            
            # Add media type if present
            media_type = msg.get('media_type', '')
            
            # Add sender info
            sender = msg.get('from', '')
            
            # Parse prayer components
            prayer_result, prayer_type, prayer_arg1, prayer_arg2 = self.parse_prayer_components(prayer_result)
            
            # Only add rows where a prayer is detected (not "No") and it's a true prayer (not a false positive)
            if (prayer_result != "No" and 
                not any(negative_pattern in prayer_result.lower() for negative_pattern in [
                    "does not contain", 
                    "no prayer", 
                    "not contain any",
                    "output format - no",
                    "not detected",
                    "therefore, no",
                    "message is just",
                    "the message"
                ])):
                # Build row
                row = {
                    'timestamp': timestamp,
                    'date': timestamp.strftime('%Y-%m-%d'),
                    'time': timestamp.strftime('%H:%M:%S'),
                    'hour': timestamp.hour,
                    'weekday': timestamp.strftime('%A'),
                    'month': timestamp.strftime('%B'),
                    'year': timestamp.year,
                    'text': target_text,
                    'context': context_text[:500] + '...' if len(context_text) > 500 else context_text,  # Include a snippet of context
                    'prayer': prayer_result,
                    'prayer_type': prayer_type,
                    'prayer_arg1': prayer_arg1,
                    'prayer_arg2': prayer_arg2,
                    'media_type': media_type,
                    'sender': sender,
                    'message_id': msg.get('id', ''),
                    'forwarded_from': msg.get('forwarded_from', ''),
                    'date_unixtime': msg.get('date_unixtime', '')
                }
                
                processed_data.append(row)
            
            # Add a small delay to prevent overloading Ollama
            time.sleep(0.5)
        
        # Display prayer statistics
        logger.info("\nPrayer Statistics:")
        logger.info(f"Total messages analyzed: {len(messages_to_process)}")
        logger.info(f"Messages without prayers: {prayer_counts.get('No', 0)}")
        logger.info(f"Messages with prayers: {len(processed_data)}")
        
        # Show detected prayer types - filter out false positives
        prayer_types = {k: v for k, v in prayer_counts.items() 
                       if k != "No" and 
                       not k.startswith("Error:") and
                       not any(pattern in k.lower() for pattern in [
                           "does not contain", 
                           "no prayer", 
                           "not contain any",
                           "output format",
                           "the message",
                           "therefore",
                           "not detected",
                           "not a prayer"
                       ])}
        if prayer_types:
            logger.info("\nDetected Prayer Types:")
            for prayer_type, count in prayer_types.items():
                logger.info(f"- {prayer_type}: {count}")
        
        # Sort by timestamp (oldest first)
        processed_data.sort(key=lambda x: x['timestamp'])
        
        return processed_data
    
    def parse_prayer_components(self, prayer_result: str) -> Tuple[str, str, str, str]:
        """Parse a prayer result into prayer type and arguments
        
        Returns:
            Tuple of (original_prayer_string, prayer_type, arg1, arg2)
        """
        if prayer_result == "No":
            return ("No", "", "", "")
        
        # Add additional check for common negative response patterns
        negative_patterns = [
            "does not contain",
            "no prayer",
            "not contain any",
            "output format - no",
            "no tokens",
            "not detected",
            "therefore, no",
            "not relate to",
            "does not match",
            "is not a prayer"
        ]
        
        if any(pattern in prayer_result.lower() for pattern in negative_patterns):
            if self.verbose:
                logger.info(f"Reclassified as NO based on content: {prayer_result[:50]}...")
            return ("No", "", "", "")
        
        # Try to match a bracketed format
        bracket_match = re.match(r'\[(.*?)\]', prayer_result)
        if bracket_match:
            # Split the bracket contents by comma
            components = [comp.strip() for comp in bracket_match.group(1).split(',', 2)]
            
            # Extract components with safe defaults
            prayer_type = components[0] if len(components) > 0 else ""
            arg1 = components[1] if len(components) > 1 else ""
            arg2 = components[2] if len(components) > 2 else ""
            
            return (prayer_result, prayer_type, arg1, arg2)
        
        # If not in bracket format, return the original with empty components
        return (prayer_result, "", "", "")
    
    def save_to_csv(self, data: List[Dict[str, Any]], base_filename: Optional[str] = None) -> str:
        """Save the data to a CSV file with fallback options if the file is locked"""
        if not data:
            logger.warning("No data to save")
            return ""
            
        if base_filename is None:
            # Generate default output path
            file_name = os.path.basename(self.file_path)
            base_filename = os.path.splitext(file_name)[0]
            
        # Path for output file
        csv_path = os.path.join(self.output_dir, f"{base_filename}_prayers.csv")
        
        # Define column order - streamlined for readability
        # All fields are still kept in the data dictionary for processing
        # but we only write the most relevant ones to the CSV
        columns = [
            # 'timestamp',  # Redundant with date and time
            'date', 'time', 'hour', 'weekday', 'month', 'year',
            'text', 'context', 'prayer', 'prayer_type', 'prayer_arg1', 'prayer_arg2'
            # 'media_type',  # Not needed for text analysis
            # 'sender',      # Always the same person
            # 'message_id',  # Technical detail not needed for analysis
            # 'forwarded_from', # Technical detail not needed for analysis
            # 'date_unixtime'   # Technical detail not needed for analysis
        ]
        
        # Try to save to main file, but have fallbacks
        original_path = csv_path
        
        # Try up to 3 alternative filenames if needed
        for attempt in range(4):
            try:
                if attempt > 0:
                    # Create alternative filename for fallback attempts
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_path = os.path.join(self.output_dir, f"{base_filename}_prayers_{timestamp}.csv")
                    logger.info(f"Trying alternative file name: {csv_path}")
                
                # Try exclusive creation first (fails if file exists)
                try:
                    with open(csv_path, 'x', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(data)
                except FileExistsError:
                    # File exists, try to open for writing instead
                    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                        writer.writeheader()
                        writer.writerows(data)
                
                logger.info(f"Data saved as CSV: {csv_path}")
                
                # If we used an alternative filename, let the user know
                if attempt > 0:
                    logger.info(f"NOTE: Used alternative filename because original ({original_path}) was inaccessible.")
                    logger.info(f"If you want to view in Excel, make sure to close any open instances of the CSV file first.")
                
                return csv_path
                
            except PermissionError as e:
                if attempt == 0:
                    logger.warning(f"File {csv_path} is open in another program or locked. Trying to save with a different name...")
                elif attempt < 3:
                    logger.warning(f"Still can't save file. Trying again with a different name...")
                else:
                    logger.error(f"All attempts to save CSV failed due to permission errors. Close any programs that might have the file open.")
                    return ""
            except Exception as e:
                logger.error(f"Error saving CSV: {e}")
                # For any other error, don't retry, just report and return
                return ""
                
        # If we get here, all attempts failed
        return ""
    
    def process(self, max_messages: int = 10) -> str:
        """Load data, process messages with prayer analysis, and save to CSV"""
        if not self.load_data():
            return ""
            
        logger.info(f"Processing messages with prayer analysis (max_messages={max_messages})...")
        data = self.process_messages(max_messages)
        
        logger.info(f"Processed {len(data)} messages")
        
        # Print sample data
        if data:
            # Calculate time span
            start_date = data[0]['timestamp']
            end_date = data[-1]['timestamp']
            days = (end_date - start_date).days
            
            logger.info(f"\nTime span: {start_date.date()} to {end_date.date()} ({days} days)")
            
            # Print sample
            logger.info("\nSample messages with prayer analysis:")
            for i, msg in enumerate(data[:3]):
                logger.info(f"{i+1}. [{msg['timestamp']}] Prayer: {msg['prayer']}")
                logger.info(f"   Text: {msg['text'][:50]}...")
            
        # Save to CSV
        return self.save_to_csv(data)

def check_ollama_availability() -> bool:
    """Check if Ollama is available and the model is installed"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            return True
        return False
    except requests.exceptions.RequestException:
        return False

def load_existing_results(csv_path: str) -> Dict[int, str]:
    """Load existing prayer results from a CSV file, indexed by message_id"""
    results = {}
    
    if not os.path.exists(csv_path):
        return results
        
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'message_id' in row and 'prayer' in row:
                    try:
                        message_id = int(row['message_id'])
                        prayer = row['prayer']
                        results[message_id] = prayer
                    except (ValueError, TypeError):
                        continue
        
        logger.info(f"Loaded {len(results)} existing prayer results from {csv_path}")
        return results
    except Exception as e:
        logger.warning(f"Error loading existing results: {e}")
        return {}

def main():
    """Main entry point"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Telegram messages for prayers using Ollama')
    parser.add_argument('--json', help='Path to Telegram JSON file', default="result.json")
    parser.add_argument('--prayers', help='Path to Prayer Wishlist file', default="Prayer Wishlist.txt")
    parser.add_argument('--model', 
                      help=f'Ollama model to use (available: {", ".join(MODEL_TIMEOUTS.keys())})', 
                      default=DEFAULT_MODEL)
    parser.add_argument('--max', type=int, help='Maximum number of messages to analyze (most recent)', default=10)
    parser.add_argument('--continue', dest='continue_analysis', action='store_true',
                      help='Continue analysis from existing CSV, skipping already processed messages')
    parser.add_argument('--reanalyze', dest='reanalyze_all', action='store_true',
                      help='Re-analyze all messages, even if already processed')
    parser.add_argument('--context-before', type=int, help='Number of messages before target to include as context', default=3)
    parser.add_argument('--context-after', type=int, help='Number of messages after target to include as context', default=2)
    parser.add_argument('--smart-context', action='store_true',
                      help='Use AI to dynamically select relevant context messages')
    parser.add_argument('--context-method', type=str, choices=['llm', 'time', 'hybrid'],
                      help='Method for smart context selection (llm, time, or hybrid)', default='llm')
    parser.add_argument('--max-context-before', type=int, 
                      help='Maximum messages before to consider for smart context selection', default=10)
    parser.add_argument('--max-context-after', type=int,
                      help='Maximum messages after to consider for smart context selection', default=10)
    parser.add_argument('--timeout', type=int,
                      help='Base timeout in seconds for API calls (automatically adjusted based on model)',
                      default=60)
    parser.add_argument('--verbose', action='store_true',
                      help='Enable verbose logging of model inputs and outputs')
    args = parser.parse_args()
    
    # Resolve file paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = args.json if os.path.isabs(args.json) else os.path.join(script_dir, args.json)
    prayer_path = args.prayers if os.path.isabs(args.prayers) else os.path.join(script_dir, args.prayers)
    
    # Calculate the output CSV path
    output_dir = os.path.dirname(json_path)
    base_filename = os.path.splitext(os.path.basename(json_path))[0]
    csv_path = os.path.join(output_dir, f"{base_filename}_prayers.csv")
    
    # Check if files exist
    if not os.path.exists(json_path):
        logger.error(f"JSON file not found: {json_path}")
        sys.exit(1)
    
    if not os.path.exists(prayer_path):
        logger.error(f"Prayer Wishlist file not found: {prayer_path}")
        sys.exit(1)
    
    # Check Ollama availability
    if not check_ollama_availability():
        logger.error("""
Ollama is not available. Please make sure:
1. Ollama is installed (https://ollama.ai/download)
2. Ollama is running (ollama serve)
3. The model is installed (ollama pull llama3.2:latest)
        """)
        sys.exit(1)
    
    # Load existing results if continuing analysis
    existing_results = {}
    if args.continue_analysis and not args.reanalyze_all and os.path.exists(csv_path):
        existing_results = load_existing_results(csv_path)
        if existing_results:
            logger.info(f"Will skip {len(existing_results)} already processed messages")
    
    # Create and run the analyzer
    logger.info(f"Processing Telegram data from: {json_path}")
    logger.info(f"Using Prayer Wishlist from: {prayer_path}")
    logger.info(f"Using Ollama model: {args.model}")
    logger.info(f"Maximum messages to analyze: {args.max}")
    logger.info(f"Continue mode: {args.continue_analysis}")
    logger.info(f"Reanalyze all: {args.reanalyze_all}")
    logger.info(f"Verbose logging: {args.verbose}")
    
    if args.smart_context:
        logger.info(f"Using SMART context selection with method '{args.context_method}' (max {args.max_context_before} before, {args.max_context_after} after)")
    else:
        logger.info(f"Using FIXED context window: {args.context_before} messages before, {args.context_after} messages after")
    
    processor = TelegramPrayerCSV(
        file_path=json_path, 
        prayer_context_path=prayer_path, 
        model=args.model,
        context_before=args.context_before,
        context_after=args.context_after,
        smart_context=args.smart_context,
        max_context_before=args.max_context_before,
        max_context_after=args.max_context_after,
        base_timeout=args.timeout,
        verbose=args.verbose,
        context_method=args.context_method
    )
    
    # Inject existing results into the processor
    if existing_results:
        processor.existing_results = existing_results
    
    csv_path = processor.process(args.max)
    
    if csv_path:
        logger.info("\nAnalysis complete!")
        logger.info(f"CSV file created at: {csv_path}")
        logger.info(f"The CSV file contains timestamps, message text, context, and prayer analysis.")
    else:
        logger.error("\nAnalysis failed to save CSV file!")
        logger.error("Possible solutions:")
        logger.error("1. Close any programs that might have the file open (Excel, LibreOffice, etc.)")
        logger.error("2. Check if you have write permissions to the directory")
        logger.error("3. If using OneDrive/Dropbox/etc., make sure files are fully synced")
        logger.error("4. Try running with a different output filename: --json alternative_name.json")

if __name__ == "__main__":
    main()