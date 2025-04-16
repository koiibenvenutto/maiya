"""
Notion page and block retrieval operations.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from maia.notion.client import notion_client
from maia.utils.config import get_last_sync_time

# Cache for blocks to avoid redundant API calls
block_cache = {}

async def get_database_properties(database_id: str):
    """
    Get all properties from a Notion database.
    
    Args:
        database_id: ID of the Notion database
        
    Returns:
        Dictionary of property names and types
    """
    try:
        database = await notion_client.databases.retrieve(database_id=database_id)
        properties = database.get("properties", {})
        
        return {
            prop_name: prop_info.get("type", "unknown")
            for prop_name, prop_info in properties.items()
        }
    except Exception as e:
        print(f"Error getting database properties: {str(e)}")
        return {}

async def query_database(database_id: str, filter_condition=None, sort_condition=None, start_cursor=None, page_size=100):
    """
    Query a Notion database with optional filter and sort conditions.
    
    Args:
        database_id: ID of the Notion database
        filter_condition: Optional filter to apply to the query
        sort_condition: Optional sort to apply to the query
        start_cursor: Optional pagination cursor
        page_size: Number of results per page (max 100)
        
    Returns:
        List of page objects from the database
    """
    query_params = {
        "database_id": database_id,
        "page_size": page_size
    }
    
    if filter_condition:
        query_params["filter"] = filter_condition
        
    if sort_condition:
        query_params["sorts"] = sort_condition
        
    if start_cursor:
        query_params["start_cursor"] = start_cursor
    
    # Get the first page of results
    response = await notion_client.databases.query(**query_params)
    results = response["results"]
    
    # If there are more results, paginate through them
    while response.get("has_more", False) and response.get("next_cursor"):
        query_params["start_cursor"] = response["next_cursor"]
        response = await notion_client.databases.query(**query_params)
        results.extend(response["results"])
    
    return results

async def get_sync_pages(database_id: str, sync_property: str = "Sync"):
    """
    Get all pages from the specified Notion database 
    where the specified sync property is checked true.
    
    Args:
        database_id: ID of the Notion database
        sync_property: Name of the checkbox property to filter by (default: "Sync")
        
    Returns:
        List of page objects with the specified sync property=true
    """
    filter_condition = {
        "property": sync_property,
        "checkbox": {
            "equals": True
        }
    }
    
    return await query_database(database_id, filter_condition)

async def get_pages_edited_after(database_id: str, timestamp: str, sync_property: str = "Sync"):
    """
    Get all pages from the specified Notion database that were edited after
    the given timestamp and have the sync property checked true.
    
    Args:
        database_id: ID of the Notion database
        timestamp: ISO format timestamp to filter by last_edited_time
        sync_property: Name of the checkbox property to filter by (default: "Sync")
        
    Returns:
        List of page objects that match the criteria
    """
    # Create a compound filter for both sync property and last edited time
    filter_condition = {
        "and": [
            {
                "property": sync_property,
                "checkbox": {
                    "equals": True
                }
            },
            {
                "timestamp": "last_edited_time",
                "last_edited_time": {
                    "after": timestamp
                }
            }
        ]
    }
    
    # Sort by last edited time descending
    sort_condition = [
        {
            "timestamp": "last_edited_time",
            "direction": "descending"
        }
    ]
    
    return await query_database(database_id, filter_condition, sort_condition)

async def get_pages_by_date(database_id: str, days: int = 30):
    """
    Get pages from the specified database within the last specified days.
    
    The function will create a filter that:
    1. Gets pages with a "Date" property within the last specified days AND
    2. Includes pages that were last edited since the last sync time
    
    Args:
        database_id: ID of the Notion database
        days: Number of days to look back
        
    Returns:
        List of page objects within the date range and/or edited since last sync
    """
    # Calculate the date for our rolling window
    days_ago = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Get the last sync time
    last_sync = get_last_sync_time()
    
    if last_sync:
        # If we have a last sync time, use a compound filter for both date range AND edited since last sync
        filter_condition = {
            "or": [
                {
                    # Pages with a date in our rolling window
                    "property": "Date", 
                    "date": {
                        "on_or_after": days_ago
                    }
                },
                {
                    # Pages edited since last sync regardless of date
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "after": last_sync
                    }
                }
            ]
        }
    else:
        # If no last sync time, just use the date range filter
        filter_condition = {
            "property": "Date", 
            "date": {
                "on_or_after": days_ago
            }
        }
    
    # Sort by date descending
    sort_condition = [
        {
            "property": "Date", 
            "direction": "descending"
        }
    ]
    
    print(f"Querying database with filter: {filter_condition}")
    
    return await query_database(database_id, filter_condition, sort_condition)

async def get_page_title(page_id: str) -> str:
    """
    Get the title of a Notion page.
    
    Args:
        page_id: ID of the Notion page
        
    Returns:
        Title of the page as a string
    """
    try:
        page = await notion_client.pages.retrieve(page_id=page_id)
        
        # Try different common title property names
        title_property_names = ["Title", "Name", "title", "name"]
        
        for prop_name in title_property_names:
            title_property = page["properties"].get(prop_name, {})
            if title_property.get("type") == "title":
                title_objects = title_property.get("title", [])
                if title_objects:
                    title = title_objects[0].get("text", {}).get("content", "")
                    if title:
                        return title
        
        # If we couldn't find a title, try to get the first heading from the content
        blocks = await get_block_content(page_id)
        for block in blocks:
            if block["type"] in ["heading_1", "heading_2", "heading_3"]:
                heading_text = "".join([
                    span.get("text", {}).get("content", "")
                    for span in block[block["type"]].get("rich_text", [])
                ])
                if heading_text:
                    return heading_text
        
        # If all else fails, use the page ID as part of the title
        return f"Page {page_id[:8]}"
    except Exception as e:
        print(f"Error getting page title: {str(e)}")
        return f"Untitled {page_id[:8]}"

async def get_block_content(block_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all blocks from a page or block including nested blocks.
    
    Args:
        block_id: ID of the block or page
        
    Returns:
        List of block objects with their content
    """
    # Check if we already have this block in the cache
    if block_id in block_cache:
        return block_cache[block_id]
    
    blocks = []
    has_more = True
    start_cursor = None

    while has_more:
        response = await notion_client.blocks.children.list(
            block_id=block_id,
            start_cursor=start_cursor,
            page_size=100,  # Get maximum blocks per request
        )
        new_blocks = response["results"]
        blocks.extend(new_blocks)
        has_more = response["has_more"]
        if has_more:
            start_cursor = response["next_cursor"]

    # Process nested blocks recursively
    async def process_block(block):
        block_type = block["type"]
        
        # Handle synced blocks
        if block_type == "synced_block":
            synced_from = block["synced_block"].get("synced_from")
            if synced_from is None:
                # This is an original synced block - process its children normally
                pass
            else:
                # This is a duplicate synced block - get the original block's content
                original_block_id = synced_from["block_id"]
                # Get the original block's content
                original_block = await notion_client.blocks.retrieve(block_id=original_block_id)
                # Process the original block instead
                return await process_block(original_block)
        
        if block.get("has_children"):
            try:
                # Get nested blocks directly
                nested_blocks = []
                has_more = True
                start_cursor = None
                
                # Create tasks for all nested blocks
                tasks = []
                
                while has_more:
                    response = await notion_client.blocks.children.list(
                        block_id=block["id"],
                        start_cursor=start_cursor,
                        page_size=100
                    )
                    new_nested_blocks = response["results"]
                    
                    # Create tasks for processing each nested block
                    for nested_block in new_nested_blocks:
                        tasks.append(process_block(nested_block))
                    
                    has_more = response["has_more"]
                    if has_more:
                        start_cursor = response["next_cursor"]
                
                # Wait for all tasks to complete
                if tasks:
                    nested_blocks = await asyncio.gather(*tasks)
                
                block["children"] = nested_blocks
            except Exception as e:
                print(f"Error fetching nested blocks for {block['id']}: {str(e)}")
        return block

    # Process all blocks that have children
    processed_blocks = []
    tasks = []
    for block in blocks:
        tasks.append(process_block(block))
    
    if tasks:
        processed_blocks = await asyncio.gather(*tasks)
    
    # Cache the processed blocks
    block_cache[block_id] = processed_blocks
    
    return processed_blocks

def clear_block_cache():
    """Clear the block cache to free memory and ensure fresh data."""
    global block_cache
    block_cache = {}

async def update_webflow_id(page_id: str, webflow_id: str, property_name: str = "Webflow ID") -> bool:
    """
    Update the Webflow ID property of a Notion page.
    
    Args:
        page_id: ID of the Notion page
        webflow_id: Webflow item ID to store
        property_name: Name of the property to update (default: "Webflow ID")
        
    Returns:
        True if the update was successful, False otherwise
    """
    try:
        # Prepare the update payload
        update_payload = {
            "properties": {
                property_name: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": webflow_id
                            }
                        }
                    ]
                }
            }
        }
        
        # Update the page
        updated_page = await notion_client.pages.update(
            page_id=page_id,
            **update_payload
        )
        
        print(f"  ✓ Updated Webflow ID in Notion: {webflow_id}")
        return True
    except Exception as e:
        print(f"  ✗ Error updating Webflow ID in Notion: {str(e)}")
        return False 