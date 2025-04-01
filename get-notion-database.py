from notion_client import Client
from dotenv import load_dotenv
import os
import re
import json
import asyncio
from datetime import datetime, timezone, timedelta
import glob

# Load environment variables from .env file
load_dotenv()

# Get your Notion token from the environment
notion_token = os.getenv("NOTION_TOKEN")

# Replace with your Notion integration token
# The client is a class of the notion SDK (software development kit) that knows everything about connecting to the Notion API/server and taken the auth token as an argument
notion = Client(auth=notion_token)

# Create output directory if it doesn't exist
OUTPUT_DIR = "notion-pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# File to store last sync time
LAST_SYNC_FILE = "last_sync.json"

def get_last_sync_time():
    """Get the last successful sync time."""
    try:
        if os.path.exists(LAST_SYNC_FILE):
            with open(LAST_SYNC_FILE, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data['last_sync'])
    except Exception as e:
        print(f"Error reading last sync time: {str(e)}")
    return None

def update_last_sync_time():
    """Update the last successful sync time."""
    try:
        current_time = datetime.now(timezone.utc)
        with open(LAST_SYNC_FILE, 'w') as f:
            json.dump({'last_sync': current_time.isoformat()}, f)
        print(f"Updated last sync time to: {current_time}")
    except Exception as e:
        print(f"Error updating last sync time: {str(e)}")

def get_page_title(page_id):
    """Get the title of a Notion page."""
    try:
        page = notion.pages.retrieve(page_id=page_id)
        # Get the first property that is a title
        for prop_name, prop in page["properties"].items():
            if prop["type"] == "title":
                title = "".join([span["text"]["content"] for span in prop["title"]])
                # Clean the title to match Notion's export format
                title = re.sub(
                    r'[<>:"/\\|?*]', "", title
                )  # Remove invalid filename characters
                return title
    except Exception as e:
        print(f"Error getting page title: {str(e)}")
    return "Untitled"


def get_page_content(page_id):
    """Fetch all blocks from a page efficiently."""
    blocks = []
    has_more = True
    start_cursor = None

    while has_more:
        response = notion.blocks.children.list(
            block_id=page_id,
            start_cursor=start_cursor,
            page_size=100,  # Get maximum blocks per request
        )
        blocks.extend(response["results"])
        has_more = response["has_more"]
        if has_more:
            start_cursor = response["next_cursor"]

    # Process nested blocks in parallel
    import aiohttp
    import ssl

    # Create SSL context for macOS
    ssl_context = ssl.create_default_context()
    # TODO Figure out how to make sure I'm doing this securely at some point cuase right now the security is turned off ⬇️
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async def fetch_nested_blocks(block):
        if block["has_children"]:
            nested_blocks = await get_page_content_async(block["id"])
            block["children"] = nested_blocks

    async def get_page_content_async(page_id, max_retries=3):
        """Get page content with retry logic."""
        blocks = []
        has_more = True
        start_cursor = None

        connector = aiohttp.TCPConnector(ssl=ssl_context, limit=10)  # Limit concurrent connections
        async with aiohttp.ClientSession(connector=connector) as session:
            while has_more:
                url = f"https://api.notion.com/v1/blocks/{page_id}/children"
                params = {"page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor

                headers = {
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                }

                for attempt in range(max_retries):
                    try:
                        async with session.get(url, params=params, headers=headers) as response:
                            if response.status == 504:
                                if attempt < max_retries - 1:
                                    print(f"Timeout fetching blocks for {page_id}, retrying...")
                                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                                    continue
                                else:
                                    print(f"Failed to fetch blocks for {page_id} after {max_retries} attempts")
                                    return blocks
                            
                            data = await response.json()
                            blocks.extend(data["results"])
                            has_more = data["has_more"]
                            if has_more:
                                start_cursor = data["next_cursor"]
                            break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            print(f"Error fetching blocks for {page_id}, retrying... ({str(e)})")
                            await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            print(f"Failed to fetch blocks for {page_id} after {max_retries} attempts: {str(e)}")
                            return blocks

        # Fetch nested blocks in parallel with a limit
        tasks = []
        for block in blocks:
            if block["has_children"]:
                tasks.append(fetch_nested_blocks(block))
        
        # Process nested blocks in smaller batches to avoid overwhelming the API
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            if batch:
                await asyncio.gather(*batch)
                await asyncio.sleep(0.5)  # Small delay between batches

        return blocks

    # Run the async function
    blocks = asyncio.run(get_page_content_async(page_id))
    return blocks


def block_to_markdown(block, level=0):
    """Convert a Notion block to markdown format."""
    block_type = block["type"]
    content = block[block_type]
    markdown = ""
    indent = "    " * level

    try:
        if block_type == "paragraph":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"{indent}{text}\n\n"
        elif block_type == "heading_1":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"# {text}\n\n"
        elif block_type == "heading_2":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"## {text}\n\n"
        elif block_type == "heading_3":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"### {text}\n\n"
        elif block_type == "bulleted_list_item":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"{indent}- {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "numbered_list_item":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"{indent}1. {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "code":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            language = content.get("language", "")
            markdown = f"```{language}\n{text}\n```\n\n"
        elif block_type == "to_do":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            checked = "x" if content.get("checked", False) else " "
            markdown = f"{indent}- [{checked}] {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "toggle":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"{indent}<details>\n{indent}<summary>{text}</summary>\n\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
            markdown += f"{indent}</details>\n\n"
        elif block_type == "divider":
            markdown = "---\n\n"
        elif block_type == "quote":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            markdown = f"{indent}> {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    child_md = block_to_markdown(child, level + 1)
                    markdown += f"{indent}> " + child_md.replace("\n", f"\n{indent}> ")
            markdown += "\n"
        elif block_type == "callout":
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            color = content.get("color", "default")
            markdown = f"{indent}> [!{color}]\n{indent}> {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    child_md = block_to_markdown(child, level + 1)
                    markdown += f"{indent}> " + child_md.replace("\n", f"\n{indent}> ")
            markdown += "\n"
        elif block_type == "image":
            # Skip image blocks since they won't be accessible to AI models
            return ""
        else:
            # Handle any nested blocks even for unknown block types
            markdown = ""
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)

        return markdown
    except Exception as e:
        print(f"Error processing block type {block_type}: {str(e)}")
        return ""


def get_page_markdown(page_id):
    """Get all blocks from a page and convert them to markdown."""
    blocks = get_page_content(page_id)
    markdown = ""
    for block in blocks:
        markdown += block_to_markdown(block)
    return markdown


def save_page_to_file(page_id, markdown_content):
    """Save a page's markdown content to a file with the correct naming convention."""
    # Get the page title
    title = get_page_title(page_id)

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

def get_date_filter():
    """Get the date filter for the last 30 days."""
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    return {"property": "Date", "date": {"on_or_after": thirty_days_ago}}

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

def main():
    # Get last sync time
    last_sync = get_last_sync_time()
    print(f"Last sync time: {last_sync if last_sync else 'Never'}")
    
    # Get existing page IDs
    existing_page_ids = get_existing_page_ids()
    print(f"Found {len(existing_page_ids)} existing pages")
    
    # Query the database for all pages from the last 60 days
    database = notion.databases.query(
        database_id="259700448ad145849e67fa1040a0e120",
        filter=get_date_filter(),
    )
    
    # Get all page IDs
    all_page_ids = [page["id"] for page in database["results"]]
    
    # Find missing pages
    missing_page_ids = [pid for pid in all_page_ids if pid not in existing_page_ids]
    
    # For existing pages, check their last_edited_time in parallel
    async def check_page_updates():
        updated_page_ids = []
        tasks = []
        
        for page_id in existing_page_ids:
            tasks.append(check_page_update(page_id))
        
        # Process in batches of 10 to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            if batch:
                results = await asyncio.gather(*batch, return_exceptions=True)
                for result in results:
                    if isinstance(result, str):  # If it's a page ID
                        updated_page_ids.append(result)
                await asyncio.sleep(0.5)  # Small delay between batches
        
        return updated_page_ids
    
    async def check_page_update(page_id):
        try:
            page = notion.pages.retrieve(page_id=page_id)
            last_edited = datetime.fromisoformat(page["last_edited_time"].replace("Z", "+00:00"))
            if last_sync and last_edited > last_sync:
                return page_id
        except Exception as e:
            print(f"Error checking last edited time for page {page_id}: {str(e)}")
        return None
    
    # Run the async check for updates
    updated_page_ids = asyncio.run(check_page_updates())
    
    # Combine updated and missing pages
    pages_to_sync = list(set(updated_page_ids + missing_page_ids))
    
    if not pages_to_sync:
        print("No pages to sync.")
    else:
        print(f"\nFound {len(pages_to_sync)} pages to sync:")
        if updated_page_ids:
            print(f"- {len(updated_page_ids)} updated pages")
        if missing_page_ids:
            print(f"- {len(missing_page_ids)} missing pages")
        
        # Process pages in parallel batches
        async def process_pages():
            tasks = []
            for page_id in pages_to_sync:
                tasks.append(process_page(page_id))
            
            # Process in batches of 5
            batch_size = 5
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                if batch:
                    await asyncio.gather(*batch)
                    await asyncio.sleep(0.5)
        
        async def process_page(page_id):
            print(f"\nProcessing page: {page_id}")
            markdown_content = get_page_markdown(page_id)
            save_page_to_file(page_id, markdown_content)
            print("-" * 80)
        
        # Run the async processing
        asyncio.run(process_pages())
    
    # Clean up old pages
    cleanup_old_pages()
    
    # Update last sync time after successful sync
    update_last_sync_time()
    print("\nSync completed successfully!")


if __name__ == "__main__":
    main()
