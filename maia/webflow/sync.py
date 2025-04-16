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
import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import shutil

from maia.notion.pages import get_sync_pages, get_pages_edited_after, get_block_content, get_page_title, update_webflow_id
from maia.html.converter import page_to_html
from maia.webflow.client import webflow_client, WebflowClient
from maia.utils.config import update_last_sync_time, get_last_sync_time

# Default database IDs from environment variables
DEFAULT_NOTION_DATABASE_ID = os.getenv("NOTION_WEBFLOW_DATABASE_ID")
DEFAULT_WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")

# Mapping between Notion property names and Webflow field names
DEFAULT_FIELD_MAPPING = {
    "Name": "name",              # Required
    "Slug": "slug",              # Required
    "Publish Date": "publish-date",     # DateTime
    "Author Name": "author-name",       # PlainText
    "Tag": "tag",                # PlainText
    "Emoji Tags": "emoji-tags",  # PlainText
    "Description": "post-summary",      # PlainText
    "Thumbnail Image": "main-image",    # Image
    "Featured": "featured",      # Switch
    "Webflow ID": "webflow-id"   # Internal use only
}

def truncate_url(url: str, max_length: int = 60) -> str:
    """Truncate a URL for display in logs."""
    if not url or len(url) <= max_length:
        return url
    
    # Split into parts
    parts = url.split('://')
    if len(parts) < 2:
        return url[:max_length-3] + '...'
    
    protocol = parts[0]
    rest = parts[1]
    
    # Calculate how much space we have left
    remaining = max_length - len(protocol) - 6  # 6 = len('://...') + len('...')
    
    # If not enough space, just do basic truncation
    if remaining < 10:
        return url[:max_length-3] + '...'
    
    # Divide remaining space between start and end of the URL
    start_length = remaining // 2
    end_length = remaining - start_length
    
    return f"{protocol}://{rest[:start_length]}...{rest[-end_length:]}"

def process_html_images(html_content: str, page_id: str) -> str:
    """
    Process all images in HTML content, uploading them to Webflow and replacing URLs.
    The formatted HTML must follow Webflow's RichText field requirements.
    
    Args:
        html_content: HTML content containing images
        page_id: ID of the page (used to create unique filenames)
        
    Returns:
        HTML content with Notion image URLs replaced with Webflow URLs in proper format
    """
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all image tags
    images = soup.find_all('img')
    print(f"Found {len(images)} images in content")
    
    # Keep track of processed images to avoid duplicates
    processed_urls = {}
    
    # Process each image
    for img in images:
        src = img.get('src')
        
        # Skip if no src attribute or already processed
        if not src or src in processed_urls:
            if src in processed_urls:
                img['src'] = processed_urls[src]
            continue
        
        # Skip if image is already on Webflow
        if 'webflow.com' in src or 'website-files.com' in src:
            continue
        
        try:
            # Generate a unique filename for the image
            parsed_url = urllib.parse.urlparse(src)
            original_filename = os.path.basename(parsed_url.path)
            
            # Create a hash from the URL to ensure uniqueness
            url_hash = hashlib.md5(src.encode()).hexdigest()[:8]
            
            # Create a filename with page ID and hash
            if '.' in original_filename:
                name, ext = os.path.splitext(original_filename)
                filename = f"{page_id[:8]}_{url_hash}{ext}"
            else:
                filename = f"{page_id[:8]}_{url_hash}.jpg"
            
            print(f"Processing image: {truncate_url(src)} -> {filename}")
            
            # Upload the image to Webflow
            result = webflow_client.upload_asset_from_url(src, filename)
            
            if result and 'url' in result:
                # Get the new URL from Webflow
                new_url = result['url']
                
                # Create a new figure element with the proper Webflow structure
                # This follows the structure required by Webflow's RichText field
                figure = soup.new_tag('figure')
                figure['class'] = 'w-richtext-figure-type-image w-richtext-align-fullwidth'
                
                # Create a new img element with the Webflow URL
                new_img = soup.new_tag('img')
                new_img['src'] = new_url
                
                # Add alt text if present
                if img.get('alt'):
                    new_img['alt'] = img.get('alt')
                    
                # Add the image to the figure
                figure.append(new_img)
                
                # Create a figcaption if there's a title
                if img.get('title'):
                    figcaption = soup.new_tag('figcaption')
                    figcaption.string = img.get('title')
                    figure.append(figcaption)
                
                # Replace the original img with the figure
                img.replace_with(figure)
                
                # Keep track of this URL
                processed_urls[src] = new_url
                print(f"  ✓ Replaced image URL: {truncate_url(src)} -> {truncate_url(new_url)}")
            else:
                print(f"  ✗ Failed to upload image: {truncate_url(src)}")
        except Exception as e:
            print(f"  ✗ Error processing image {truncate_url(src)}: {str(e)}")
    
    # Return the updated HTML content
    return str(soup)

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
    
    # Get page properties - adding defensive check
    properties = page.get("properties", {}) if page else {}
    if not properties:
        raise ValueError(f"Page has no properties or is malformed")
        
    webflow_data = {}
    
    # Extract the page ID
    page_id = page.get("id", "") if page else ""
    if not page_id:
        raise ValueError(f"Page has no ID")
    
    # Extract Webflow ID if it exists
    webflow_id = None
    if "Webflow ID" in properties:
        webflow_id_prop = properties["Webflow ID"]
        if webflow_id_prop and webflow_id_prop.get("type") == "rich_text":
            rich_text = webflow_id_prop.get("rich_text", [])
            if rich_text:
                webflow_id = "".join([text.get("plain_text", "") for text in rich_text if text])
                if webflow_id and webflow_id.strip():
                    # Store Webflow ID (not sent to Webflow API, but used for syncing)
                    webflow_data["_webflow_id"] = webflow_id.strip()
    
    # Get the page title from the Name property
    if "Name" in properties:
        name_prop = properties["Name"]
        if name_prop and name_prop.get("type") == "title":
            title_array = name_prop.get("title", [])
            if title_array:
                title = "".join([text.get("plain_text", "") for text in title_array if text])
                if title:
                    webflow_data[field_mapping.get("Name", "name")] = title
                else:
                    raise ValueError(f"Page title is empty")
            else:
                raise ValueError(f"Page title array is empty")
        else:
            raise ValueError(f"Name property has unexpected format")
    else:
        # If Name property is missing, this is a required field - throw an error
        raise ValueError(f"Missing required field: Name")
    
    # Generate slug if not present
    slug_field = field_mapping.get("Slug", "slug")
    if "Slug" in properties:
        slug_prop = properties["Slug"]
        if slug_prop and slug_prop.get("type") == "rich_text":
            # Get slug from rich text
            rich_text = slug_prop.get("rich_text", [])
            if rich_text:
                slug = "".join([text.get("plain_text", "") for text in rich_text if text])
                if slug:
                    webflow_data[slug_field] = slug
                else:
                    webflow_data[slug_field] = slugify(title)
            else:
                webflow_data[slug_field] = slugify(title)
        else:
            webflow_data[slug_field] = slugify(title)
    else:
        webflow_data[slug_field] = slugify(title)
    
    # Process date field
    date_field = field_mapping.get("Publish Date", "publish-date")
    if "Publish Date" in properties:
        date_prop = properties["Publish Date"]
        if date_prop and date_prop.get("type") == "date":
            date_value = date_prop.get("date")
            if date_value and date_value.get("start"):
                # Format the date for Webflow (ISO format)
                webflow_data[date_field] = date_value.get("start")
    
    # If no date is found, use current date
    if date_field not in webflow_data or not webflow_data.get(date_field):
        current_date = datetime.now().isoformat().split("T")[0]  # Format as YYYY-MM-DD
        webflow_data[date_field] = current_date
    
    # Process author field
    author_field = field_mapping.get("Author Name", "author-name")
    if "Author Name" in properties:
        author_prop = properties["Author Name"]
        if author_prop and author_prop.get("type") == "rich_text":
            rich_text = author_prop.get("rich_text", [])
            if rich_text:
                author = "".join([text.get("plain_text", "") for text in rich_text if text])
                if author:
                    webflow_data[author_field] = author
                else:
                    # Use a default author name if empty
                    webflow_data[author_field] = "Anonymous"
            else:
                webflow_data[author_field] = "Anonymous"
        else:
            webflow_data[author_field] = "Anonymous"
    else:
        # Use a default author if missing
        webflow_data[author_field] = "Anonymous"
    
    # Process tag field
    tag_field = field_mapping.get("Tag", "tag")
    if "Tag" in properties:
        tag_prop = properties["Tag"]
        if tag_prop and tag_prop.get("type") == "select":
            select = tag_prop.get("select")
            if select:
                tag_name = select.get("name")
                if tag_name:
                    webflow_data[tag_field] = tag_name
    
    # Process emoji tags field
    emoji_tags_field = field_mapping.get("Emoji Tags", "emoji-tags")
    if "Emoji Tags" in properties:
        emoji_prop = properties["Emoji Tags"]
        if emoji_prop and emoji_prop.get("type") == "rich_text":
            rich_text = emoji_prop.get("rich_text", [])
            if rich_text:
                emoji_tags = "".join([text.get("plain_text", "") for text in rich_text if text])
                if emoji_tags:
                    webflow_data[emoji_tags_field] = emoji_tags
    
    # Process description field (for post-summary)
    description_field = field_mapping.get("Description", "post-summary")
    if "Description" in properties:
        desc_prop = properties["Description"]
        if desc_prop and desc_prop.get("type") == "rich_text":
            rich_text = desc_prop.get("rich_text", [])
            if rich_text:
                description = "".join([text.get("plain_text", "") for text in rich_text if text])
                if description:
                    webflow_data[description_field] = description
    
    # Process featured image field as Webflow asset
    image_field = field_mapping.get("Thumbnail Image", "main-image")
    if "Thumbnail Image" in properties:
        img_prop = properties["Thumbnail Image"]
        if img_prop and img_prop.get("type") == "files":
            files = img_prop.get("files", [])
            if files and len(files) > 0:
                file = files[0]
                if file:
                    image_url = None
                    
                    if file.get("type") == "external":
                        external = file.get("external")
                        if external:
                            image_url = external.get("url", "")
                    elif file.get("type") == "file":
                        file_obj = file.get("file")
                        if file_obj:
                            image_url = file_obj.get("url", "")
                    
                    if image_url:
                        # Use the Notion URL directly for the main image
                        # Notion URLs are stable so we don't need to re-upload
                        webflow_data[image_field] = image_url
                        print(f"  ✓ Using Notion thumbnail image URL directly: {truncate_url(image_url)}")
    
    # Handle page cover image if present but no thumbnail was provided
    if image_field not in webflow_data and page and "cover" in page:
        cover = page.get("cover", {})
        if cover:
            image_url = None
            
            if cover.get("type") == "external":
                external = cover.get("external")
                if external:
                    image_url = external.get("url", "")
            elif cover.get("type") == "file":
                file_obj = cover.get("file")
                if file_obj:
                    image_url = file_obj.get("url", "")
                    
            if image_url:
                # Use the cover image URL directly 
                webflow_data[image_field] = image_url
                print(f"  ✓ Using Notion page cover image URL directly: {truncate_url(image_url)}")
    
    # Process featured field (checkbox)
    featured_field = field_mapping.get("Featured", "featured")
    if "Featured" in properties:
        featured_prop = properties["Featured"]
        if featured_prop and featured_prop.get("type") == "checkbox":
            webflow_data[featured_field] = featured_prop.get("checkbox", False)
    
    try:
        # Get page content
        blocks = await get_block_content(page_id)
        
        # Convert blocks to HTML
        html_content = page_to_html(blocks)
        
        # Process images in the HTML content
        processed_html = process_html_images(html_content, page_id)
        
        # Set HTML content field - always supported
        webflow_data["post-body"] = processed_html
    except Exception as e:
        # If there's an error with content processing, just use a placeholder
        print(f"  ✗ Error processing content: {str(e)}")
        webflow_data["post-body"] = f"<p>Content unavailable. Please check the original Notion page.</p>"
    
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
                         sync_property: str = "Sync",
                         force_update: bool = False) -> Tuple[int, int, int]:
    """
    Sync Notion pages to Webflow CMS.
    
    Args:
        notion_database_id: ID of the Notion database (default to env var)
        webflow_collection_id: ID of the Webflow collection (default to env var)
        field_mapping: Custom mapping of Notion property names to Webflow field names
        sync_property: Name of the checkbox property to filter by (default: "Sync")
        force_update: Force update of all items regardless of edit time
        
    Returns:
        Tuple of (created_count, updated_count, error_count)
    """
    # Use default IDs if none provided
    notion_database_id = notion_database_id or DEFAULT_NOTION_DATABASE_ID or WEBFLOW_CMS_DATABASE_ID
    webflow_collection_id = webflow_collection_id or DEFAULT_WEBFLOW_COLLECTION_ID
    
    if not notion_database_id:
        raise ValueError("No Notion database ID provided. Please specify or set NOTION_WEBFLOW_DATABASE_ID environment variable.")
    
    if not webflow_collection_id:
        raise ValueError("No Webflow collection ID provided. Please specify or set WEBFLOW_COLLECTION_ID environment variable.")
    
    # Get last sync time
    last_sync = get_last_sync_time()
    print(f"Last sync time: {last_sync or 'Never'}")
    
    # Get pages where sync property is checked true
    print(f"Getting pages from Notion database {notion_database_id} with {sync_property}=true...")
    try:
        pages = await get_sync_pages(notion_database_id, sync_property)
    except Exception as e:
        print(f"Error getting pages from Notion: {str(e)}")
        return (0, 0, 1)
    
    if not pages:
        print(f"No pages found with {sync_property}=true")
        return (0, 0, 0)
    
    print(f"Found {len(pages)} pages to sync to Webflow")
    
    # Get all existing items in Webflow for comparison
    print(f"Getting all current items from Webflow collection...")
    try:
        webflow_items = webflow_client.get_collection_items(webflow_collection_id)
        if webflow_items is None:
            webflow_items = []
        print(f"Found {len(webflow_items)} existing items in Webflow")
    except Exception as e:
        print(f"Error getting Webflow items: {str(e)}")
        webflow_items = []
        print("Proceeding with empty Webflow item list")
    
    # Create a map of Webflow IDs to items for faster lookup
    webflow_id_map = {item["id"]: item for item in webflow_items if item and "id" in item}
    
    # Track Notion page IDs and processed Webflow IDs
    notion_page_ids = [page["id"] for page in pages if page and "id" in page]
    processed_webflow_ids = []
    
    # Get collection schema to validate against required fields
    try:
        collection_fields = webflow_client.get_collection_fields(webflow_collection_id)
        if collection_fields is None:
            collection_fields = {}
        required_fields = [field_slug for field_slug, field_info in collection_fields.items() 
                          if field_info and field_info.get("required")]
        print(f"Required fields in Webflow collection: {required_fields}")
    except Exception as e:
        print(f"Error getting collection fields: {str(e)}")
        required_fields = []
        print("Proceeding without required field validation")
    
    # Track counts
    created_count = 0
    updated_count = 0
    error_count = 0
    deleted_count = 0
    skipped_count = 0
    
    # Create a map of Notion pages with their Webflow IDs for reference
    notion_webflow_id_map = {}
    
    # First pass: identify all Webflow IDs that are stored in Notion pages
    for page in pages:
        if not page or "id" not in page:
            continue
            
        page_id = page["id"]
        properties = page.get("properties", {})
        if not properties:
            continue
        
        # Extract Webflow ID if it exists
        if "Webflow ID" in properties:
            webflow_id_prop = properties["Webflow ID"]
            if webflow_id_prop and webflow_id_prop.get("type") == "rich_text":
                rich_text = webflow_id_prop.get("rich_text", [])
                if rich_text:
                    webflow_id = "".join([text.get("plain_text", "") for text in rich_text if text])
                    if webflow_id and webflow_id.strip():
                        notion_webflow_id_map[page_id] = webflow_id.strip()
    
    # Process each page
    for i, page in enumerate(pages, 1):
        if not page or "id" not in page:
            print(f"\n[{i}/{len(pages)}] Skipping invalid page (no ID)")
            error_count += 1
            continue
            
        page_id = page["id"]
        try:
            # Get the last edited time of the page
            last_edited_time = page.get("last_edited_time")
            
            print(f"\n[{i}/{len(pages)}] Processing page: {page_id}")
            print(f"  Last edited time: {last_edited_time}")
            
            # Convert Notion page to Webflow item
            try:
                webflow_data, stored_webflow_id = await notion_to_webflow_item(page, field_mapping)
            except Exception as e:
                print(f"  ✗ Error converting page to Webflow format: {str(e)}")
                error_count += 1
                continue
            
            # Get the slug for reference
            slug = webflow_data.get("slug", "")
            if not slug:
                # Generate a slug if it's empty
                title = webflow_data.get("name", f"Page {page_id[:8]}")
                slug = slugify(title)
                webflow_data["slug"] = slug
            
            print(f"  Page slug: {slug}")
            
            # Validate required fields
            missing_fields = []
            for field in required_fields:
                if field not in webflow_data or not webflow_data.get(field):
                    missing_fields.append(field)
            
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                print(f"  ✗ {error_msg}")
                raise ValueError(error_msg)
            
            # ONLY try to find existing item by Webflow ID - DO NOT use slug matching
            existing_item = None
            existing_item_id = None
            
            if stored_webflow_id and stored_webflow_id in webflow_id_map:
                # If we have a Webflow ID in Notion and it exists in Webflow, use it
                print(f"  Found item by Webflow ID: {stored_webflow_id}")
                existing_item = webflow_id_map[stored_webflow_id]
                existing_item_id = stored_webflow_id
                
                # Track that we've processed this Webflow ID
                processed_webflow_ids.append(existing_item_id)
                
                # Always update the content if force_update is True or if the item was edited after the last sync
                should_update = force_update or last_sync is None or (last_edited_time and last_edited_time > last_sync)
                
                if should_update:
                    # Update existing item
                    print(f"  Updating existing item: {existing_item_id}")
                    try:
                        response = webflow_client.update_item(webflow_collection_id, existing_item_id, webflow_data)
                        if response:
                            updated_count += 1
                            print(f"  ✓ Updated item: {slug}")
                        else:
                            print(f"  ✗ Update failed: Empty response")
                            error_count += 1
                    except Exception as e:
                        print(f"  ✗ Error updating item: {str(e)}")
                        error_count += 1
                else:
                    # Skip update as the page hasn't been edited since last sync
                    print(f"  ✓ Skipping update for unchanged item: {slug}")
                    skipped_count += 1
            else:
                # Create new item if no Webflow ID or if ID not found in Webflow
                print(f"  Creating new live item with slug: {slug}")
                try:
                    response = webflow_client.create_item(webflow_collection_id, webflow_data)
                    if not response:
                        print(f"  ✗ Create failed: Empty response")
                        error_count += 1
                        continue
                        
                    # Items created with the live endpoint are already published
                    item_id = response.get("id")
                    
                    if item_id:
                        # Track this published item
                        processed_webflow_ids.append(item_id)
                        
                        # Update Notion with the Webflow ID
                        print(f"  Updating Notion page with new Webflow ID: {item_id}")
                        success = await update_webflow_id(page_id, item_id)
                        if not success:
                            print(f"  ✗ Warning: Failed to update Webflow ID in Notion")
                        
                        created_count += 1
                        print(f"  ✓ Created live item: {slug}")
                    else:
                        print(f"  ✗ Create succeeded but no item ID returned")
                        error_count += 1
                except Exception as e:
                    print(f"  ✗ Error creating item: {str(e)}")
                    error_count += 1
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
            if not webflow_item or "id" not in webflow_item:
                continue
                
            webflow_id = webflow_item.get("id")
            webflow_slug = webflow_item.get("slug", "Unknown")
            
            # If the ID isn't in our list of processed Webflow IDs, delete it
            if webflow_id and webflow_id not in processed_webflow_ids:
                try:
                    print(f"  Deleting item '{webflow_slug}' (ID: {webflow_id}) from Webflow...")
                    deleted = webflow_client.delete_item(webflow_collection_id, webflow_id)
                    if deleted:
                        deleted_count += 1
                        print(f"  ✓ Deleted item: {webflow_slug} (ID: {webflow_id})")
                    else:
                        print(f"  ✗ Delete operation failed")
                        error_count += 1
                except Exception as e:
                    print(f"  ✗ Error deleting item {webflow_slug}: {str(e)}")
                    error_count += 1
    
    print(f"\nSync completed: {created_count} created, {updated_count} updated, {skipped_count} skipped, {deleted_count} deleted, {error_count} errors")
    
    # Update last sync time after successful sync
    new_sync_time = update_last_sync_time()
    print(f"Updated last sync time to: {new_sync_time}")
    
    return (created_count, updated_count, error_count) 