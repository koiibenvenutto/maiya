from notion_client import AsyncClient
from dotenv import load_dotenv
import os
import re
import json
import asyncio
from datetime import datetime, timezone, timedelta
import glob
import requests
import argparse
from typing import List, Dict, Any, Optional

# Load environment variables from .env file
load_dotenv()

# Get your Notion token from the environment
notion_token = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Replace with your Notion integration token
# The client is a class of the notion SDK (software development kit) that knows everything about connecting to the Notion API/server and taken the auth token as an argument
notion = AsyncClient(auth=notion_token)

# Create output directory if it doesn't exist
OUTPUT_DIR = "notion-pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File to store last sync time
SYNC_TIME_FILE = "sync_config.json"

# Cache for blocks to avoid redundant API calls
block_cache = {}

async def get_last_sync_time():
    """Get the last sync time from the file."""
    if os.path.exists(SYNC_TIME_FILE):
        try:
            # First try to read as JSON
            with open(SYNC_TIME_FILE, 'r') as f:
                content = f.read().strip()
                try:
                    data = json.loads(content)
                    return data.get('last_sync')
                except json.JSONDecodeError:
                    # If it's not valid JSON, assume it's just a timestamp string
                    # This handles the old format
                    return content
        except Exception as e:
            print(f"Error reading last sync time: {str(e)}")
    return None

def update_last_sync_time():
    """Update the last sync time to now."""
    current_time = datetime.now(timezone.utc)
    config_data = {}
    
    # Read existing config if it exists
    if os.path.exists(SYNC_TIME_FILE):
        try:
            with open(SYNC_TIME_FILE, 'r') as f:
                content = f.read().strip()
                try:
                    config_data = json.loads(content)
                except json.JSONDecodeError:
                    # If it's not valid JSON, assume it's just a timestamp string
                    # This handles the old format
                    config_data = {'last_sync': content}
        except Exception as e:
            print(f"Error reading config file: {str(e)}")
    
    # Update the last_sync time
    config_data['last_sync'] = current_time.isoformat()
    
    # Write the updated config back to the file
    with open(SYNC_TIME_FILE, 'w') as f:
        json.dump(config_data, f)

async def get_page_title(page_id):
    """Get the title of a page from Notion."""
    try:
        page = await notion.pages.retrieve(page_id=page_id)
        
        # Debug: Print all property names to help identify the title property
        print(f"Available properties: {list(page['properties'].keys())}")
        
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

async def get_block_content(block_id):
    """Fetch all blocks from a page or block including nested blocks."""
    # Check if we already have this block in the cache
    if block_id in block_cache:
        return block_cache[block_id]
    
    blocks = []
    has_more = True
    start_cursor = None

    while has_more:
        response = await notion.blocks.children.list(
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
                original_block = await notion.blocks.retrieve(block_id=original_block_id)
                # Process the original block instead
                return await process_block(original_block)
        
        if block.get("has_children"):
            try:
                # Get nested blocks directly using blocks.children.list
                nested_blocks = []
                has_more = True
                start_cursor = None
                
                # Create tasks for all nested blocks
                tasks = []
                
                while has_more:
                    response = await notion.blocks.children.list(
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


def block_to_markdown(block, level=0):
    """Convert a Notion block to markdown format."""
    block_type = block["type"]
    content = block[block_type]
    markdown = ""
    indent = "    " * level

    try:
        # Extract text content from any block type
        if block_type == "code":
            # For code blocks, get text from the code property's rich_text
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            
            # Get code block properties
            language = content.get("language", "")
            
            # Format the code block with language specification
            markdown = f"{indent}```{language}\n"
            
            # Add the code content with proper indentation
            code_lines = text.split("\n")
            for line in code_lines:
                markdown += f"{indent}{line}\n"
            
            # Close the code block
            markdown += f"{indent}```\n"  # Add line break after code block
            
            # Add caption if present (safely handle empty caption array)
            caption_text = ""
            if content.get("caption"):
                caption_text = "".join(
                    [
                        span.get("text", {}).get("content", "")
                        for span in content["caption"]
                    ]
                )
            if caption_text:
                markdown += f"{indent}*{caption_text}*\n"  # Add line break after caption
        else:
            # For other blocks, get text from the block's rich_text with formatting
            text = ""
            for span in content.get("rich_text", []):
                # Get the text content
                span_text = span.get("text", {}).get("content", "")
                
                # Apply formatting based on annotations
                annotations = span.get("annotations", {})
                
                # Apply formatting in a specific order to avoid conflicts
                if annotations.get("strikethrough", False):
                    span_text = f"~~{span_text}~~"
                if annotations.get("underline", False):
                    span_text = f"<u>{span_text}</u>"
                if annotations.get("italic", False):
                    span_text = f"*{span_text}*"
                if annotations.get("bold", False):
                    span_text = f"**{span_text}**"
                
                # Add the formatted text
                text += span_text

            # Format the block based on its type and state
            if block_type == "heading_1":
                markdown = f"{indent}# {text}\n"  # Add line break after heading
            elif block_type == "heading_2":
                markdown = f"{indent}## {text}\n"  # Add line break after heading
            elif block_type == "heading_3":
                markdown = f"{indent}### {text}\n"  # Add line break after heading
            elif block_type == "bulleted_list_item":
                markdown = f"{indent}- {text}\n"  # Add line break after list item
            elif block_type == "numbered_list_item":
                markdown = f"{indent}1. {text}\n"  # Add line break after list item
            elif block_type == "to_do":
                checked = "x" if content.get("checked", False) else " "
                markdown = f"{indent}- [{checked}] {text}\n"  # Add line break after to-do
            elif block_type == "toggle":
                # Preserve toggle state in metadata
                is_toggled = content.get("is_toggled", False)
                markdown = f"{indent}<details{' open' if is_toggled else ''}>\n{indent}    <summary>{text}</summary>\n"
            elif block_type == "quote":
                # Handle block quotes with proper indentation
                markdown = f"{indent}> {text}\n"  # Add line break after quote
                # If the quote has children, they should be indented further
                if block.get("children"):
                    child_indent = indent + "> "
                    child_markdowns = []
                    for child in block["children"]:
                        child_markdown = block_to_markdown(child, level + 1)
                        if child_markdown:  # Only add if there's actual content
                            # Add quote marker to each line of child content
                            child_markdown = "\n".join([f"{child_indent}{line}" for line in child_markdown.split("\n")])
                            child_markdowns.append(child_markdown)
                    if child_markdowns:  # Only add newline if there are children
                        markdown += "\n".join(child_markdowns) + "\n"  # Add line break after children
            elif block_type == "callout":
                # Get callout properties
                color = content.get("color", "default")
                icon = content.get("icon", {}).get("emoji", "ℹ️")
                
                # Format the callout with icon and color
                markdown = f"{indent}> [!{color} {icon}]\n{indent}> {text}\n"  # Add line break after callout
                
                # Handle nested content in callouts
                if block.get("children"):
                    child_indent = indent + "> "
                    child_markdowns = []
                    for child in block["children"]:
                        child_markdown = block_to_markdown(child, level + 1)
                        if child_markdown:  # Only add if there's actual content
                            # Add callout marker to each line of child content
                            child_markdown = "\n".join([f"{child_indent}{line}" for line in child_markdown.split("\n")])
                            child_markdowns.append(child_markdown)
                    if child_markdowns:  # Only add newline if there are children
                        markdown += "\n".join(child_markdowns) + "\n"  # Add line break after children
            elif block_type == "divider":
                markdown = f"{indent}---\n"  # Add line break after divider
            elif block_type == "image":
                # Skip image blocks since they won't be accessible to AI models
                return ""
            else:
                # Default case for paragraph and unknown types
                markdown = f"{indent}{text}\n"  # Add line break after paragraph

        # Process children for any block type except quotes, callouts, and code blocks (already handled above)
        if block.get("children") and block_type not in ["quote", "callout", "code"]:
            child_markdowns = []
            for child in block["children"]:
                child_markdown = block_to_markdown(child, level + 1)
                if child_markdown:  # Only add if there's actual content
                    child_markdowns.append(child_markdown)
            
            if child_markdowns:  # Only add newline if there are children
                markdown += "\n".join(child_markdowns)  # Don't add extra newline here

        # Close toggle blocks
        if block_type == "toggle":
            markdown += f"{indent}</details>\n"  # Add line break after toggle

        # Only add a newline if there's actual content and it's not a child block
        if markdown and level == 0:
            # Clean up multiple consecutive newlines
            markdown = re.sub(r'\n{3,}', '\n\n', markdown)
            # Ensure there's exactly one newline at the end
            markdown = markdown.rstrip() + '\n'

        return markdown
    except Exception as e:
        print(f"Error processing block type {block_type}: {str(e)}")
        return ""


async def get_page_markdown(page_id):
    """Get all blocks from a page and convert them to markdown."""
    blocks = await get_block_content(page_id)
    markdown = ""
    for block in blocks:
        block_markdown = block_to_markdown(block)
        if block_markdown:
            markdown += block_markdown
    
    # Clean up any remaining multiple consecutive newlines
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    # Ensure there's exactly one newline at the end
    markdown = markdown.rstrip() + '\n'
    
    return markdown


async def save_page_to_file(page_id, markdown_content):
    """Save a page's markdown content to a file with the correct naming convention."""
    # Get the page title
    title = await get_page_title(page_id)

    # Create the filename
    filename = f"{title} {page_id}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    # Save the content
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"Saved {filename}")
    return filepath


def get_existing_page_ids():
    """Get list of page IDs from existing markdown files."""
    existing_ids = set()
    for file in os.listdir(OUTPUT_DIR):
        if file.endswith('.md'):
            # Extract page ID from filename (last part after the last space)
            page_id = file.split()[-1].replace('.md', '')
            existing_ids.add(page_id)
    return existing_ids

def get_date_filter(days=30):
    """Get the date filter for the specified number of days."""
    days_ago = (datetime.now() - timedelta(days=days)).isoformat()
    return {"property": "Date", "date": {"on_or_after": days_ago}}

def cleanup_old_pages():
    """Remove markdown files for pages older than 30 days."""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    removed_count = 0
    for file in os.listdir(OUTPUT_DIR):
        if file.endswith('.md'):
            filepath = os.path.join(OUTPUT_DIR, file)
            # Get file modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < thirty_days_ago:
                try:
                    os.remove(filepath)
                    removed_count += 1
                    print(f"Removed old file: {file}")
                except Exception as e:
                    print(f"Error removing {file}: {str(e)}")
    
    if removed_count > 0:
        print(f"\nCleaned up {removed_count} old files")
    return removed_count

async def process_page(page_id, index, total):
    """Process a single page and save it to a file."""
    print(f"\n[{index}/{total}] Processing page: {page_id}")
    
    # Clear the block cache for this page to ensure we get fresh data
    block_cache.clear()
    
    # Get the page content and convert to markdown
    markdown_content = await get_page_markdown(page_id)
    
    # Save the page to a file
    await save_page_to_file(page_id, markdown_content)
    
    print(f"[{index}/{total}] ✓ Completed page: {page_id}")
    print("-" * 80)

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Sync Notion pages to markdown files')
    parser.add_argument('--days', type=int, default=30, help='Number of days to look back for pages')
    args = parser.parse_args()
    
    # Get last sync time
    last_sync = await get_last_sync_time()
    print(f"Last sync time: {last_sync if last_sync else 'Never'}")
    
    # Get existing page IDs
    existing_page_ids = get_existing_page_ids()
    print(f"Found {len(existing_page_ids)} existing pages")
    
    # DEBUG MODE: Uncomment to sync only a specific page for debugging
    # target_page_id = "1cad13396967802f898be5165518f20f"
    # pages_to_sync = [target_page_id]
    # print(f"\nDEBUG MODE: Syncing specific page: {target_page_id}")
    
    # PRODUCTION MODE: Sync pages from the specified number of days
    print(f"\nSyncing pages from the last {args.days} days")
    
    # Query the database for pages from the specified number of days
    date_filter = get_date_filter(days=args.days)
    response = await notion.databases.query(
        database_id=DATABASE_ID,
        filter=date_filter,
        sorts=[{"property": "Date", "direction": "descending"}]
    )
    
    # Get page IDs from the response
    pages_to_sync = [page["id"] for page in response["results"]]
    print(f"Found {len(pages_to_sync)} pages to sync")
    
    # Clean up old pages that are no longer in the database
    cleanup_old_pages()
    
    # Process pages sequentially to avoid memory issues
    for i, page_id in enumerate(pages_to_sync, 1):
        await process_page(page_id, i, len(pages_to_sync))
    
    # Update last sync time after successful sync
    update_last_sync_time()
    print("\nSync completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
