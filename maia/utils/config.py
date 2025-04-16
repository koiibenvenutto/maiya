"""
Configuration management for Maia.
"""
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Configuration file for storing settings
CONFIG_FILE = "sync_config.json"

def get_config() -> Dict[str, Any]:
    """
    Get the current configuration.
    
    Returns:
        Configuration dictionary
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                content = f.read().strip()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # If it's not valid JSON, assume it's just a timestamp string
                    # This handles the old format
                    return {'last_sync': content}
        except Exception as e:
            print(f"Error reading config file: {str(e)}")
    
    # Return default config if no file exists or there was an error
    return {
        'last_sync': None,
        'last_days': 5,  # Default to 5 days for sync
        'chat_context_days': 5  # Default to 5 days for chat context
    }

def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the configuration with new values.
    
    Args:
        updates: Dictionary of configuration values to update
        
    Returns:
        Updated configuration dictionary
    """
    # Get current config
    config = get_config()
    
    # Update with new values
    config.update(updates)
    
    # Save updated config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    
    return config

def update_last_sync_time() -> str:
    """
    Update the last sync time to now.
    
    Returns:
        Current time as ISO format string
    """
    current_time = datetime.now(timezone.utc)
    iso_time = current_time.isoformat()
    
    update_config({'last_sync': iso_time})
    
    return iso_time

def get_last_sync_time() -> Optional[str]:
    """
    Get the last sync time.
    
    Returns:
        Last sync time as ISO format string or None if not set
    """
    config = get_config()
    return config.get('last_sync')

def get_sync_days_setting() -> int:
    """
    Get the number of days to look back for Notion sync.
    
    Returns:
        Number of days as integer
    """
    config = get_config()
    return config.get('last_days', 5)  # Default to 5 days

def set_sync_days_setting(days: int) -> int:
    """
    Set the number of days to look back for Notion sync.
    
    Args:
        days: Number of days to look back
        
    Returns:
        The days value that was set
    """
    if days <= 0:
        days = 1  # Ensure a minimum of 1 day
    
    update_config({'last_days': days})
    
    return days

def get_chat_days_setting() -> int:
    """
    Get the number of days to look back for chat context.
    
    Returns:
        Number of days as integer
    """
    config = get_config()
    return config.get('chat_context_days', 5)  # Default to 5 days

def set_chat_days_setting(days: int) -> int:
    """
    Set the number of days to look back for chat context.
    
    Args:
        days: Number of days to look back
        
    Returns:
        The days value that was set
    """
    if days <= 0:
        days = 1  # Ensure a minimum of 1 day
    
    update_config({'chat_context_days': days})
    
    return days

# Legacy functions for backward compatibility - these will be removed in a future version
def get_days_setting() -> int:
    """
    Get the number of days to look back for content.
    DEPRECATED: Use get_sync_days_setting() or get_chat_days_setting() instead.
    
    Returns:
        Number of days as integer
    """
    config = get_config()
    return config.get('last_days', 5)  # Default to 5 days

def set_days_setting(days: int) -> int:
    """
    Set the number of days to look back for content.
    DEPRECATED: Use set_sync_days_setting() or set_chat_days_setting() instead.
    
    Args:
        days: Number of days to look back
        
    Returns:
        The days value that was set
    """
    if days <= 0:
        days = 1  # Ensure a minimum of 1 day
    
    update_config({'last_days': days})
    
    return days 