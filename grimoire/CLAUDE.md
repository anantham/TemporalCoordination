# GRIMOIRE PROJECT NOTES

## Directory Structure
The grimoire folder contains scripts for analyzing Telegram saved messages, with a focus on prayer pattern detection.

## Main Scripts
- `fetch_saved_messages.py` - Fetches messages from Telegram using MTProto API
- `telegram_prayer_csv.py` - Analyzes messages for prayer patterns using Ollama LLM
- `analyze_json.py` - General purpose JSON structure analyzer

## Prayer Detection System
The system uses a three-layer filtering approach:
1. Primary response normalization in `analyze_prayer_with_ollama()`
2. Secondary filtering in `parse_prayer_components()`
3. Final verification before adding rows to CSV data

## Prayer Types
From Prayer Wishlist.txt:
- Meta
- SendTo
- Connect
- Privacy
- Remind
- Recommend
- Project

## Common Issues
- False positives from verbose "No" LLM responses
- Normalization patterns for negative responses include:
  - "does not contain"
  - "no prayer detected"
  - "output format - no"

## Recent Fixes
- Enhanced normalization of LLM responses
- Added secondary filtering for false positives
- Improved CSV row filtering logic
- Refined prayer counting statistics