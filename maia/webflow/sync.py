"""
Sync Notion pages to Webflow CMS.
"""
import os
import re
import asyncio
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from slugify import slugify

from maia.notion.pages import get_sync_pages, get_pages_edited_after, get_block_content, get_page_title, update_webflow_id
from maia.html.converter import page_to_html
from maia.webflow.client import webflow_client, WebflowClient
from maia.utils.config import update_last_sync_time, get_last_sync_time

# Default database IDs from environment variables
DEFAULT_NOTION_DATABASE_ID = os.getenv("NOTION_WEBFLOW_DATABASE_ID")
DEFAULT_WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")

# Mapping between Notion property names and Webflow field names
DEFAULT_FIELD_MAPPING = {
    "Name": "name",             # Required
    "Slug": "slug",             # Required
    "Publish Date": "publish-date",  # Optional
    "Author Name": "author-name",    # Required
    "Tag": "tag",               # Optional
    "Emoji Tags": "emoji-tags", # Optional
    "Description": "description",    # Optional
    "Thumbnail Image": "main-image", # Optional
    "Featured": "featured",      # Optional
    "Webflow ID": "webflow-id"  # Optional - used for syncing
}

async def notion_to_webflow_item(page: Dict[str, Any], field_mapping: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Convert a Notion page to a Webflow CMS item format.
    
    Args:
        page: Notion page object
        field_mapping: Optional custom mapping of Notion property names to Webflow field names
        
    Returns:
        Webflow item data ready to be posted to the API
    """
    # Use default mapping if none provided
    if field_mapping is None:
        field_mapping = DEFAULT_FIELD_MAPPING
    
    # Get page properties
    properties = page.get("properties", {})
    webflow_data = {}
    
    # Extract the page ID
    page_id = page.get("id", "")
    
    # Extract Webflow ID if it exists
    webflow_id = None
    if "Webflow ID" in properties and properties["Webflow ID"].get("type") == "rich_text":
        rich_text = properties["Webflow ID"].get("rich_text", [])
        if rich_text:
            webflow_id = "".join([text.get("plain_text", "") for text in rich_text])
            if webflow_id.strip():
                # Store Webflow ID (not sent to Webflow API, but used for syncing)
                webflow_data["_webflow_id"] = webflow_id.strip()
    
    # Get the page title from the Name property
    if "Name" in properties and properties["Name"].get("type") == "title":
        title_array = properties["Name"].get("title", [])
        title = "".join([text.get("plain_text", "") for text in title_array])
        webflow_data[field_mapping.get("Name", "name")] = title
    else:
        title = await get_page_title(page_id)
        webflow_data[field_mapping.get("Name", "name")] = title
    
    # Generate slug if not present
    slug_field = field_mapping.get("Slug", "slug")
    if "Slug" in properties and properties["Slug"].get("type") == "rich_text":
        # Get slug from rich text
        rich_text = properties["Slug"].get("rich_text", [])
        if rich_text:
            slug = "".join([text.get("plain_text", "") for text in rich_text])
            if slug:
                webflow_data[slug_field] = slug
            else:
                webflow_data[slug_field] = slugify(title)
        else:
            webflow_data[slug_field] = slugify(title)
    else:
        webflow_data[slug_field] = slugify(title)
    
    # Process date field
    date_field = field_mapping.get("Publish Date", "publish-date")
    if "Publish Date" in properties and properties["Publish Date"].get("type") == "date":
        date_value = properties["Publish Date"].get("date")
        if date_value and date_value.get("start"):
            # Format the date for Webflow (ISO format)
            webflow_data[date_field] = date_value.get("start")
    
    # If no date is found, use current date
    if date_field not in webflow_data or not webflow_data.get(date_field):
        current_date = datetime.now().isoformat().split("T")[0]  # Format as YYYY-MM-DD
        webflow_data[date_field] = current_date
    
    # Process author field
    author_field = field_mapping.get("Author Name", "author-name")
    if "Author Name" in properties and properties["Author Name"].get("type") == "rich_text":
        rich_text = properties["Author Name"].get("rich_text", [])
        if rich_text:
            author = "".join([text.get("plain_text", "") for text in rich_text])
            webflow_data[author_field] = author
    
    # Set default author name if not found in properties
    if author_field not in webflow_data or not webflow_data.get(author_field):
        webflow_data[author_field] = "Koii Benvenutto"
    
    # Process tag field
    tag_field = field_mapping.get("Tag", "tag")
    if "Tag" in properties and properties["Tag"].get("type") == "select":
        select = properties["Tag"].get("select")
        if select:
            webflow_data[tag_field] = select.get("name", "")
    
    # Process emoji tags field
    emoji_tags_field = field_mapping.get("Emoji Tags", "emoji-tags")
    if "Emoji Tags" in properties and properties["Emoji Tags"].get("type") == "rich_text":
        rich_text = properties["Emoji Tags"].get("rich_text", [])
        if rich_text:
            emoji_tags = "".join([text.get("plain_text", "") for text in rich_text])
            webflow_data[emoji_tags_field] = emoji_tags
    
    # Process featured image field
    image_field = field_mapping.get("Thumbnail Image", "main-image")
    if "Thumbnail Image" in properties and properties["Thumbnail Image"].get("type") == "files":
        files = properties["Thumbnail Image"].get("files", [])
        if files:
            file = files[0]
            if file.get("type") == "external":
                webflow_data[image_field] = file.get("external", {}).get("url", "")
            elif file.get("type") == "file":
                webflow_data[image_field] = file.get("file", {}).get("url", "")
    
    # Process featured field (checkbox)
    featured_field = field_mapping.get("Featured", "featured")
    if "Featured" in properties and properties["Featured"].get("type") == "checkbox":
        webflow_data[featured_field] = properties["Featured"].get("checkbox", False)
    
    # Get page content
    blocks = await get_block_content(page_id)
    
    # Convert blocks to HTML
    html_content = page_to_html(blocks)
    
    # Set HTML content field - always supported
    webflow_data["post-body"] = html_content
    
    # Remove any fields that might not exist in the Webflow collection schema
    # These typically include custom fields that aren't part of the default mapping
    print(f"  Removing potentially unsupported fields")
    
    # Fields we know should be removed (based on the error)
    if "description" in webflow_data:
        print(f"  Removing 'description' field")
        del webflow_data["description"]
    
    if "notion-id" in webflow_data:
        print(f"  Removing 'notion-id' field")
        del webflow_data["notion-id"]
    
    # Remove internal fields that shouldn't be sent to Webflow
    if "_webflow_id" in webflow_data:
        # Store it separately but remove from the data to be sent
        webflow_id = webflow_data["_webflow_id"]
        del webflow_data["_webflow_id"]
        # Return a tuple of the data and the ID
        return (webflow_data, webflow_id)
    
    # If no Webflow ID, return data with None
    return (webflow_data, None)

async def sync_to_webflow(notion_database_id: str = None, 
                         webflow_collection_id: str = None,
                         field_mapping: Dict[str, str] = None,
                         sync_property: str = "Sync") -> Tuple[int, int, int]:
    """
    Sync Notion pages to Webflow CMS.
    
    Args:
        notion_database_id: ID of the Notion database (default to env var)
        webflow_collection_id: ID of the Webflow collection (default to env var)
        field_mapping: Custom mapping of Notion property names to Webflow field names
        sync_property: Name of the checkbox property to filter by (default: "Sync")
        
    Returns:
        Tuple of (created_count, updated_count, error_count)
    """
    # Use default IDs if none provided
    notion_database_id = notion_database_id or DEFAULT_NOTION_DATABASE_ID
    webflow_collection_id = webflow_collection_id or DEFAULT_WEBFLOW_COLLECTION_ID
    
    if not notion_database_id:
        raise ValueError("No Notion database ID provided. Please specify or set NOTION_WEBFLOW_DATABASE_ID environment variable.")
    
    if not webflow_collection_id:
        raise ValueError("No Webflow collection ID provided. Please specify or set WEBFLOW_COLLECTION_ID environment variable.")
    
    # Get pages where sync property is checked true
    print(f"Getting pages from Notion database {notion_database_id} with {sync_property}=true...")
    pages = await get_sync_pages(notion_database_id, sync_property)
    
    if not pages:
        print(f"No pages found with {sync_property}=true")
        return (0, 0, 0)
    
    print(f"Found {len(pages)} pages to sync to Webflow")
    
    # Get all existing items in Webflow for comparison
    print(f"Getting all current items from Webflow collection...")
    webflow_items = webflow_client.get_collection_items(webflow_collection_id)
    print(f"Found {len(webflow_items)} existing items in Webflow")
    
    # Create a map of Webflow IDs to items for faster lookup
    webflow_id_map = {item["id"]: item for item in webflow_items}
    
    # Track Notion page IDs and processed Webflow IDs
    notion_page_ids = [page["id"] for page in pages]
    processed_webflow_ids = []
    
    # Track counts
    created_count = 0
    updated_count = 0
    error_count = 0
    deleted_count = 0
    
    # Process each page
    for i, page in enumerate(pages, 1):
        page_id = page["id"]
        try:
            print(f"\n[{i}/{len(pages)}] Processing page: {page_id}")
            
            # Convert Notion page to Webflow item
            webflow_data, stored_webflow_id = await notion_to_webflow_item(page, field_mapping)
            
            # Get the slug for reference
            slug = webflow_data.get("slug", "")
            if not slug:
                # Generate a slug if it's empty
                title = webflow_data.get("name", f"Page {page_id[:8]}")
                slug = slugify(title)
                webflow_data["slug"] = slug
            
            # Try to find existing item by Webflow ID first, then by slug
            existing_item = None
            existing_item_id = None
            
            if stored_webflow_id and stored_webflow_id in webflow_id_map:
                # If we have a Webflow ID in Notion and it exists in Webflow, use it
                print(f"  Found item by Webflow ID: {stored_webflow_id}")
                existing_item = webflow_id_map[stored_webflow_id]
                existing_item_id = stored_webflow_id
            else:
                # Fallback to slug matching if no Webflow ID or not found
                print(f"  Checking if item with slug '{slug}' exists in Webflow...")
                existing_item = webflow_client.find_item_by_slug(webflow_collection_id, slug)
                if existing_item:
                    existing_item_id = existing_item.get("id")
            
            if existing_item_id:
                # Track that we've processed this Webflow ID
                processed_webflow_ids.append(existing_item_id)
                
                # Update existing item
                print(f"  Updating existing item: {existing_item_id}")
                response = webflow_client.update_item(webflow_collection_id, existing_item_id, webflow_data)
                
                # Print response details for debugging
                print(f"  Update response status: Success")
                print(f"  Response content: {json.dumps(response, indent=2)[:200]}...")
                
                # Always publish the item
                try:
                    print(f"  Publishing item: {existing_item_id}")
                    publish_response = webflow_client.publish_item(webflow_collection_id, existing_item_id)
                    print(f"  Publish response: {json.dumps(publish_response, indent=2)[:200]}...")
                    
                    # If Webflow ID wasn't stored in Notion, update it
                    if not stored_webflow_id:
                        print(f"  Notion page needs Webflow ID stored: {existing_item_id}")
                        await update_webflow_id(page_id, existing_item_id)
                
                except Exception as publish_error:
                    print(f"  Error publishing item: {str(publish_error)}")
                    if hasattr(publish_error, 'response') and hasattr(publish_error.response, 'text'):
                        try:
                            error_json = publish_error.response.json()
                            print(f"  Publish error details: {json.dumps(error_json, indent=2)}")
                        except:
                            print(f"  Publish error response: {publish_error.response.text}")
                
                updated_count += 1
                print(f"  ✓ Updated item: {slug}")
            else:
                # Create new item
                print(f"  Creating new item with slug: {slug}")
                response = webflow_client.create_item(webflow_collection_id, webflow_data)
                
                # Print response details for debugging
                print(f"  Create response status: Success")
                print(f"  Response content: {json.dumps(response, indent=2)[:200]}...")
                
                # Always publish the item
                item_id = response.get("id")  # Try with "id" instead of "_id"
                if not item_id:
                    item_id = response.get("_id")  # Try with "_id" as fallback
                
                print(f"  Extracted item ID: {item_id}")
                if item_id:
                    try:
                        print(f"  Publishing item: {item_id}")
                        publish_response = webflow_client.publish_item(webflow_collection_id, item_id)
                        print(f"  Publish response: {json.dumps(publish_response, indent=2)[:200]}...")
                    except Exception as publish_error:
                        print(f"  Error publishing item: {str(publish_error)}")
                        if hasattr(publish_error, 'response') and hasattr(publish_error.response, 'text'):
                            try:
                                error_json = publish_error.response.json()
                                print(f"  Publish error details: {json.dumps(error_json, indent=2)}")
                            except:
                                print(f"  Publish error response: {publish_error.response.text}")
                
                # Save the Webflow ID to processed list
                if item_id:
                    processed_webflow_ids.append(item_id)
                    print(f"  Updating Notion page with new Webflow ID: {item_id}")
                    await update_webflow_id(page_id, item_id)
                
                created_count += 1
                print(f"  ✓ Created item: {slug}")
        
        except Exception as e:
            print(f"  ✗ Error processing page {page_id}: {str(e)}")
            # Print more detailed error information if available
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    error_json = e.response.json()
                    print(f"  Error details: {json.dumps(error_json, indent=2)}")
                except:
                    print(f"  Error response: {e.response.text}")
            error_count += 1
        
        print("-" * 80)
    
    # Clean up items from Webflow that aren't in the processed IDs list
    if webflow_items:
        print("\nChecking for items in Webflow that should be removed...")
        for webflow_item in webflow_items:
            webflow_id = webflow_item.get("id")
            webflow_slug = webflow_item.get("slug", "Unknown")
            
            # If the ID isn't in our list of processed Webflow IDs, delete it
            if webflow_id and webflow_id not in processed_webflow_ids:
                try:
                    print(f"  Deleting item '{webflow_slug}' (ID: {webflow_id}) from Webflow...")
                    webflow_client.delete_item(webflow_collection_id, webflow_id)
                    deleted_count += 1
                    print(f"  ✓ Deleted item: {webflow_slug} (ID: {webflow_id})")
                except Exception as e:
                    print(f"  ✗ Error deleting item {webflow_slug}: {str(e)}")
                    # Only count as an error if it's not a JSON parsing issue (which means deletion was likely successful)
                    if "Expecting value" not in str(e):
                        error_count += 1
                    else:
                        # This was likely a successful deletion with an empty response
                        deleted_count += 1
                        print(f"  ✓ Item likely deleted despite parsing error: {webflow_slug} (ID: {webflow_id})")
    
    print(f"\nSync completed: {created_count} created, {updated_count} updated, {deleted_count} deleted, {error_count} errors")
    
    # Each item is published individually via the publish_item API endpoint
    # A full site publish is not required as Webflow supports publishing individual CMS items
    # This avoids unnecessary site rebuilds and preserves analytics data
    
    return (created_count, updated_count, error_count) 