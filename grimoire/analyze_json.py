#!/usr/bin/env python3
"""
JSON Analyzer - Analyzes structure, metadata, and statistics of JSON files
"""

import json
import os
import sys
from collections import Counter, defaultdict
import datetime
from typing import Any, Dict, List, Set, Tuple, Union

def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Get basic file metadata"""
    stats = os.stat(file_path)
    return {
        "file_path": file_path,
        "file_size_bytes": stats.st_size,
        "file_size_mb": round(stats.st_size / (1024 * 1024), 2),
        "last_modified": datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        "created": datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
    }

def get_type(value: Any) -> str:
    """Get a user-friendly type name"""
    if isinstance(value, dict):
        return "object"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif value is None:
        return "null"
    else:
        return str(type(value).__name__)

def analyze_value(value: Any, max_items: int = 5) -> Dict[str, Any]:
    """Analyze a single value for its type and basic statistics"""
    value_type = get_type(value)
    result = {"type": value_type}
    
    if value_type == "array":
        result["length"] = len(value)
        if len(value) > 0:
            # If all items are the same type, analyze just one
            types = [get_type(item) for item in value[:20]]  # Check first 20 items
            if len(set(types)) == 1:
                result["items_type"] = types[0]
                # If items are objects, include keys from first few items
                if types[0] == "object" and value:
                    all_keys = set()
                    for item in value[:max_items]:
                        all_keys.update(item.keys())
                    result["sample_keys"] = sorted(list(all_keys))
            else:
                result["items_types"] = dict(Counter(types))
                
            # Process sample items
            result["sample"] = value[:max_items] if len(value) <= max_items else value[:max_items]
    
    elif value_type == "object":
        keys = list(value.keys())
        result["keys_count"] = len(keys)
        result["keys"] = sorted(keys)
        
    elif value_type == "string":
        result["length"] = len(value)
        # Try to detect if it's a date
        if len(value) > 8 and any(x in value for x in [':', '-', '/', 'T']):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", 
                "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"
            ]:
                try:
                    datetime.datetime.strptime(value, fmt)
                    result["possible_format"] = "date"
                    break
                except ValueError:
                    pass
                    
    elif value_type in ["integer", "float"]:
        if isinstance(value, (list, dict)):
            pass  # Skip statistics for non-numeric
        else:
            result["value"] = value
            
    return result

def analyze_json_structure(data: Any, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
    """Analyze JSON structure recursively up to max_depth"""
    if current_depth >= max_depth:
        return {"truncated": True, "type": get_type(data)}
    
    result = analyze_value(data)
    
    # Handle recursive analysis for objects and arrays
    if result["type"] == "object" and data:
        sample_fields = {}
        for key, value in data.items():
            sample_fields[key] = analyze_json_structure(value, max_depth, current_depth + 1)
        result["fields"] = sample_fields
            
    elif result["type"] == "array" and data and len(data) > 0:
        # If array has objects, analyze first item in detail
        if get_type(data[0]) == "object":
            result["sample_item_structure"] = analyze_json_structure(data[0], max_depth, current_depth + 1)
        # For other types, just return type information
        else:
            element_type = get_type(data[0])
            result["items_type"] = element_type
            
    return result

def analyze_array_statistics(data: List[Dict]) -> Dict[str, Any]:
    """Calculate statistics for an array of objects"""
    if not data or not isinstance(data, list) or not data:
        return {"error": "Not an array or empty array"}
    
    result = {"count": len(data)}
    
    # Only analyze if we have objects
    if not all(isinstance(item, dict) for item in data[:10]):
        return {**result, "note": "Array does not contain objects, skipping detailed analysis"}
    
    # Get all possible keys
    all_keys = set()
    for item in data:
        if isinstance(item, dict):
            all_keys.update(item.keys())
    
    # Count occurrences of each key
    key_counts = {key: 0 for key in all_keys}
    for item in data:
        if isinstance(item, dict):
            for key in item.keys():
                key_counts[key] += 1
    
    # Analyze value types and statistics for each key
    key_stats = {}
    for key in all_keys:
        # Count by type
        values = [item.get(key) for item in data if isinstance(item, dict) and key in item]
        types_count = Counter(get_type(v) for v in values)
        
        # Basic stats
        stats = {
            "count": len(values),
            "types": dict(types_count),
            "present_in_percent": round(key_counts[key] / len(data) * 100, 1)
        }
        
        # Numeric stats if applicable
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        if numeric_values:
            stats["numeric"] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "avg": sum(numeric_values) / len(numeric_values),
                "count": len(numeric_values)
            }
            
        # String stats
        string_values = [v for v in values if isinstance(v, str)]
        if string_values:
            stats["string"] = {
                "min_length": min(len(s) for s in string_values),
                "max_length": max(len(s) for s in string_values),
                "avg_length": sum(len(s) for s in string_values) / len(string_values),
                "count": len(string_values)
            }
            
        # Most common values (only for reasonable size values)
        if values and all(isinstance(v, (str, int, float, bool, type(None))) for v in values[:100]):
            # Only count for non-unique fields (skip IDs)
            if len(set(values)) < len(values) * 0.8:  # If less than 80% unique
                common_values = Counter(str(v) for v in values).most_common(5)
                if common_values:
                    stats["common_values"] = common_values
        
        key_stats[key] = stats
    
    return {
        **result,
        "keys_found": len(all_keys),
        "keys": sorted(all_keys),
        "field_stats": key_stats
    }

def process_json_file(file_path: str) -> None:
    """Process a JSON file and print its analysis"""
    try:
        print(f"\n{'=' * 80}")
        print(f"Analyzing: {file_path}")
        print(f"{'=' * 80}")
        
        # Get file metadata
        metadata = get_file_metadata(file_path)
        print(f"\n[File Metadata]")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
        
        # Load JSON
        print(f"\nLoading JSON file ({metadata['file_size_mb']} MB)...")
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Basic info
        data_type = get_type(data)
        print(f"\n[Basic Structure]")
        print(f"  Root type: {data_type}")
        
        # Structure analysis
        print(f"\n[Structure Analysis]")
        structure = analyze_json_structure(data, max_depth=2)
        print(json.dumps(structure, indent=2))
        
        # Detailed statistics for arrays
        if data_type == "array" and data:
            print(f"\n[Array Statistics]")
            stats = analyze_array_statistics(data)
            
            # Print summary statistics
            print(f"  Items count: {stats.get('count', 'N/A')}")
            print(f"  Fields found: {stats.get('keys_found', 'N/A')}")
            print(f"  Fields: {', '.join(stats.get('keys', []))}")
            
            # Print field statistics 
            print(f"\n[Field Statistics]")
            for key, key_stats in stats.get('field_stats', {}).items():
                print(f"  {key}:")
                print(f"    Present in: {key_stats['present_in_percent']}% of items")
                print(f"    Types: {key_stats['types']}")
                
                if 'numeric' in key_stats:
                    num_stats = key_stats['numeric']
                    print(f"    Numeric - Min: {num_stats['min']}, Max: {num_stats['max']}, Avg: {round(num_stats['avg'], 2)}")
                
                if 'common_values' in key_stats:
                    print(f"    Common values: {key_stats['common_values']}")
                
        print(f"\n{'=' * 80}")
        print("Analysis complete!")
        print(f"{'=' * 80}\n")
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, "result.json")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
        
    process_json_file(file_path)