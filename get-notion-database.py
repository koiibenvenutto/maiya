from notion_client import Client
from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

# Get your Notion token from the environment
notion_token = os.getenv("NOTION_TOKEN")

# Replace with your Notion integration token
notion = Client(auth=notion_token)

# Create output directory if it doesn't exist
OUTPUT_DIR = "notion-pages"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_page_title(page_id):
    """Get the title of a Notion page."""
    try:
        page = notion.pages.retrieve(page_id=page_id)
        # Get the first property that is a title
        for prop_name, prop in page["properties"].items():
            if prop["type"] == "title":
                title = "".join([span["text"]["content"] for span in prop["title"]])
                # Clean the title to match Notion's export format
                title = re.sub(r'[<>:"/\\|?*]', '', title)  # Remove invalid filename characters
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
            page_size=100  # Get maximum blocks per request
        )
        blocks.extend(response["results"])
        has_more = response["has_more"]
        if has_more:
            start_cursor = response["next_cursor"]
    
    # Process nested blocks in parallel
    import asyncio
    import aiohttp
    import ssl
    
    # Create SSL context for macOS
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    async def fetch_nested_blocks(block):
        if block["has_children"]:
            nested_blocks = await get_page_content_async(block["id"])
            block["children"] = nested_blocks
    
    async def get_page_content_async(page_id):
        blocks = []
        has_more = True
        start_cursor = None
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            while has_more:
                url = f"https://api.notion.com/v1/blocks/{page_id}/children"
                params = {"page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor
                
                headers = {
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }
                
                async with session.get(url, params=params, headers=headers) as response:
                    data = await response.json()
                    blocks.extend(data["results"])
                    has_more = data["has_more"]
                    if has_more:
                        start_cursor = data["next_cursor"]
        
        # Fetch nested blocks in parallel
        tasks = [fetch_nested_blocks(block) for block in blocks if block["has_children"]]
        if tasks:
            await asyncio.gather(*tasks)
        
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
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"{indent}{text}\n\n"
        elif block_type == "heading_1":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"# {text}\n\n"
        elif block_type == "heading_2":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"## {text}\n\n"
        elif block_type == "heading_3":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"### {text}\n\n"
        elif block_type == "bulleted_list_item":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"{indent}- {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "numbered_list_item":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"{indent}1. {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "code":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            language = content.get("language", "")
            markdown = f"```{language}\n{text}\n```\n\n"
        elif block_type == "to_do":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            checked = "x" if content.get("checked", False) else " "
            markdown = f"{indent}- [{checked}] {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
        elif block_type == "toggle":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"{indent}<details>\n{indent}<summary>{text}</summary>\n\n"
            if block.get("children"):
                for child in block["children"]:
                    markdown += block_to_markdown(child, level + 1)
            markdown += f"{indent}</details>\n\n"
        elif block_type == "divider":
            markdown = "---\n\n"
        elif block_type == "quote":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
            markdown = f"{indent}> {text}\n"
            if block.get("children"):
                for child in block["children"]:
                    child_md = block_to_markdown(child, level + 1)
                    markdown += f"{indent}> " + child_md.replace("\n", f"\n{indent}> ")
            markdown += "\n"
        elif block_type == "callout":
            text = "".join([span.get("text", {}).get("content", "") for span in content.get("rich_text", [])])
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

# Replace with your actual database ID
database = notion.databases.query(
    database_id="259700448ad145849e67fa1040a0e120",
    filter={"property": "Date", "date": {"on_or_after": "2025-03-25"}},
)

# Print the raw data for now
# print(database)

page_ids = [page["id"] for page in database["results"]]

# Get markdown content for each page and save to files
for page_id in page_ids:
    print(f"\nProcessing page: {page_id}")
    markdown_content = get_page_markdown(page_id)
    save_page_to_file(page_id, markdown_content)
    print("-" * 80)
