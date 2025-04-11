#!/usr/bin/env python
"""
Command Line Interface for Maia.
"""
import os
import asyncio
import argparse
from typing import List, Dict, Any

# Import modules
from maia.notion.client import notion_client
from maia.notion.pages import get_sync_pages, get_pages_by_date, get_page_title, get_block_content, clear_block_cache, get_database_properties
from maia.markdown.converter import page_to_markdown
from maia.storage.files import save_page_to_file, get_existing_page_ids, cleanup_old_pages
from maia.utils.config import update_last_sync_time, get_last_sync_time, get_days_setting, set_days_setting

# Database ID for the Notion database (default to environment variable)
DEFAULT_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
WEBFLOW_CMS_DATABASE_ID = "10dd13396967807ab987c92a4d29b9b8"  # Database ID for Webflow CMS operations
JOURNAL_DATABASE_ID = "259700448ad145849e67fa1040a0e120"  # Specific ID for journal database

async def process_page(page_id: str, index: int, total: int):
    """
    Process a single page, convert to markdown, and save to file.
    
    Args:
        page_id: ID of the page
        index: Current index in the processing queue
        total: Total number of pages to process
    """
    print(f"\n[{index}/{total}] Processing page: {page_id}")
    
    # Clear block cache to ensure fresh data
    clear_block_cache()
    
    # Get the page title
    title = await get_page_title(page_id)
    
    # Get the page blocks
    blocks = await get_block_content(page_id)
    
    # Convert blocks to markdown
    markdown_content = page_to_markdown(blocks)
    
    # Save the page to a file
    filepath = await save_page_to_file(page_id, title, markdown_content)
    
    print(f"[{index}/{total}] ✓ Saved page to {filepath}")
    print("-" * 80)

# ==================== NOTION COMMANDS ====================

async def notion_list_properties(args):
    """List all properties in a Notion database."""
    database_id = args.database or DEFAULT_DATABASE_ID
    
    if not database_id:
        raise ValueError("No database ID provided. Please specify with --database or set NOTION_DATABASE_ID environment variable.")
    
    print(f"Getting properties from database {database_id}...")
    
    # Get the database properties
    properties = await get_database_properties(database_id)
    
    if not properties:
        print("No properties found or error retrieving database.")
        return
    
    print("\nDatabase properties:")
    for prop_name, prop_type in properties.items():
        print(f"- {prop_name} ({prop_type})")
    
    return properties

async def notion_list_sync_pages(args):
    """List pages in the database with Sync=true."""
    database_id = args.database or DEFAULT_DATABASE_ID
    sync_property = args.sync_property or "Sync"
    
    print(f"Getting pages from database {database_id} with {sync_property}=true...")
    
    # Get pages where Sync is checked true
    pages = await get_sync_pages(database_id, sync_property)
    
    # Print pages info
    print(f"Found {len(pages)} pages with {sync_property}=true")
    
    if pages:
        print("\nPages to sync:")
        for i, page in enumerate(pages, 1):
            page_id = page["id"]
            title = await get_page_title(page_id)
            print(f"{i}. {title} ({page_id})")
    
    return pages

async def notion_debug_page(args):
    """Debug a specific Notion page."""
    # Import modules
    from maia.notion.pages import get_page_title, get_block_content, clear_block_cache
    from maia.webflow.sync import notion_to_webflow_item
    
    # Get page ID
    page_id = args.page_id
    
    if not page_id:
        raise ValueError("No page ID provided. Please specify with --page-id.")
    
    print(f"Debugging Notion page {page_id}...")
    
    try:
        # Get the page from Notion API
        page = await notion_client.pages.retrieve(page_id=page_id)
        
        # Get page title
        title = await get_page_title(page_id)
        print(f"Page title: {title}")
        
        # Get raw properties
        properties = page.get("properties", {})
        print("\nRaw properties:")
        for prop_name, prop_value in properties.items():
            prop_type = prop_value.get("type", "unknown")
            print(f"- {prop_name} ({prop_type})")
        
        # Convert to Webflow item
        print("\nConverting to Webflow item...")
        webflow_data = await notion_to_webflow_item(page)
        
        # Print Webflow data
        print("\nWebflow data:")
        for field_name, field_value in webflow_data.items():
            if field_name == "post-body":
                value_preview = f"{str(field_value)[:100]}..." if field_value else "None"
                print(f"- {field_name}: {value_preview}")
            else:
                print(f"- {field_name}: {field_value}")
        
        return webflow_data
    except Exception as e:
        print(f"Error debugging page: {str(e)}")
        return None

# ==================== JOURNAL COMMANDS ====================

async def journal_sync(args):
    """Sync journal entries from Notion to local markdown files."""
    # Get database ID
    database_id = args.database or JOURNAL_DATABASE_ID
    if not database_id:
        raise ValueError("No database ID provided. Please specify with --database or set JOURNAL_DATABASE_ID environment variable.")
    
    # Get number of days
    if args.days is not None:
        days = args.days
        # Update the days setting
        set_days_setting(days)
    else:
        days = get_days_setting()
    
    # Get last sync time
    last_sync = get_last_sync_time()
    print(f"Last sync time: {last_sync or 'Never'}")
    
    # Get existing page IDs
    existing_page_ids = get_existing_page_ids()
    print(f"Found {len(existing_page_ids)} existing journal entries")
    
    print(f"\nSyncing journal entries from the last {days} days...")
    
    # Query the database for pages from the specified number of days
    pages = await get_pages_by_date(database_id, days)
    
    # Get page IDs from the response
    pages_to_sync = [page["id"] for page in pages]
    print(f"Found {len(pages_to_sync)} journal entries to sync")
    
    # Clean up old pages that are no longer in the database
    removed = cleanup_old_pages(days)
    print(f"Removed {removed} old journal entries")
    
    # Process pages sequentially to avoid memory issues
    for i, page_id in enumerate(pages_to_sync, 1):
        await process_page(page_id, i, len(pages_to_sync))
    
    # Update last sync time after successful sync
    update_last_sync_time()
    print("\nJournal sync completed successfully!")

# ==================== WEBFLOW COMMANDS ====================

async def webflow_sync(args):
    """Sync Notion pages to Webflow CMS."""
    # Import webflow sync module here to avoid circular imports
    from maia.webflow.sync import sync_to_webflow
    
    # Get database and collection IDs
    notion_database_id = args.database or WEBFLOW_CMS_DATABASE_ID  # Use Webflow CMS database ID by default
    webflow_collection_id = args.collection or os.getenv("WEBFLOW_COLLECTION_ID")
    sync_property = args.sync_property or "Sync"
    
    print(f"Syncing Webflow CMS database {notion_database_id} to Webflow collection {webflow_collection_id}...")
    
    # Run the sync function
    return await sync_to_webflow(notion_database_id, webflow_collection_id, sync_property=sync_property)

async def webflow_command(args):
    """Default command for webflow - runs sync."""
    # Create default args for sync if they don't exist
    if not hasattr(args, 'collection'):
        args.collection = None
    if not hasattr(args, 'database'):
        args.database = None
    if not hasattr(args, 'sync_property'):
        args.sync_property = None
    
    print("Running webflow sync (default command)...")
    return await webflow_sync(args)

def webflow_list_collection(args):
    """List all fields in a Webflow collection."""
    # Import the Webflow client
    from maia.webflow.client import webflow_client
    
    # Get collection ID
    collection_id = args.collection or os.getenv("WEBFLOW_COLLECTION_ID")
    
    if not collection_id:
        raise ValueError("No collection ID provided. Please specify with --collection or set WEBFLOW_COLLECTION_ID environment variable.")
    
    print(f"Getting fields from Webflow collection {collection_id}...")
    
    # Get the collection fields
    try:
        fields = webflow_client.get_collection_fields(collection_id)
        
        if not fields:
            print("No fields found in the collection.")
            return
        
        print("\nWebflow collection fields:")
        for field_slug, field_info in fields.items():
            required_str = " (required)" if field_info.get("required") else ""
            print(f"- {field_slug}: {field_info.get('name')} ({field_info.get('type')}){required_str}")
        
        return fields
    except Exception as e:
        print(f"Error getting collection fields: {str(e)}")
        return {}

# ==================== CHAT INTERFACE ====================

def chat_run(args):
    """Run the chat interface."""
    try:
        # Import the chat interface here to avoid circular imports
        from maia.chat.interface import chat
        
        # Run the chat interface
        chat()
    except ImportError as e:
        print(f"Error loading chat interface: {str(e)}")
        print("Make sure you have the required dependencies installed:")
        print("pip install anthropic openai prompt_toolkit rich")

# ==================== MAIN ENTRY POINT ====================

def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Maia CLI - Notion to Markdown and more")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # ===== JOURNAL COMMAND =====
    journal_parser = subparsers.add_parser('journal', help='Journal operations')
    journal_subparsers = journal_parser.add_subparsers(dest='subcommand', help='Journal subcommands')
    
    # Journal sync
    journal_sync_parser = journal_subparsers.add_parser('sync', help='Sync journal entries from Notion')
    journal_sync_parser.add_argument('--days', type=int, help='Number of days to look back for pages')
    journal_sync_parser.add_argument('--database', type=str, help='Notion database ID')
    journal_sync_parser.set_defaults(func=journal_sync)
    
    # ===== WEBFLOW COMMAND =====
    webflow_parser = subparsers.add_parser('webflow', help='Webflow operations')
    webflow_parser.set_defaults(func=webflow_command)  # Default function when no subcommand is provided
    webflow_subparsers = webflow_parser.add_subparsers(dest='subcommand', help='Webflow subcommands')
    
    # Webflow sync
    webflow_sync_parser = webflow_subparsers.add_parser('sync', help='Sync Notion pages to Webflow CMS')
    webflow_sync_parser.add_argument('--database', type=str, help='Notion database ID')
    webflow_sync_parser.add_argument('--collection', type=str, help='Webflow collection ID (default: WEBFLOW_COLLECTION_ID env var)')
    webflow_sync_parser.add_argument('--sync-property', type=str, help='Name of the sync property in Notion (default: "Sync")')
    webflow_sync_parser.set_defaults(func=webflow_sync)
    
    # Webflow list fields
    webflow_list_parser = webflow_subparsers.add_parser('fields', help='List all fields in a Webflow collection')
    webflow_list_parser.add_argument('--collection', type=str, help='Webflow collection ID')
    webflow_list_parser.set_defaults(func=webflow_list_collection)
    
    # ===== NOTION COMMAND =====
    notion_parser = subparsers.add_parser('notion', help='Notion operations')
    notion_subparsers = notion_parser.add_subparsers(dest='subcommand', help='Notion subcommands')
    
    # Notion list properties
    notion_properties_parser = notion_subparsers.add_parser('properties', help='List all properties in a Notion database')
    notion_properties_parser.add_argument('--database', type=str, help='Notion database ID')
    notion_properties_parser.set_defaults(func=notion_list_properties)
    
    # Notion list sync pages
    notion_list_sync_parser = notion_subparsers.add_parser('list-sync', help='List pages with Sync=true')
    notion_list_sync_parser.add_argument('--database', type=str, help='Notion database ID')
    notion_list_sync_parser.add_argument('--sync-property', type=str, help='Name of the sync property (default: "Sync")')
    notion_list_sync_parser.set_defaults(func=notion_list_sync_pages)
    
    # Notion debug page
    notion_debug_parser = notion_subparsers.add_parser('debug', help='Debug a specific Notion page')
    notion_debug_parser.add_argument('--page-id', type=str, required=True, help='Notion page ID')
    notion_debug_parser.set_defaults(func=notion_debug_page)
    
    # ===== CHAT COMMAND =====
    chat_parser = subparsers.add_parser('chat', help='Start the chat interface')
    chat_parser.set_defaults(func=chat_run)
    
    # ===== BACKWARDS COMPATIBILITY =====
    # These commands maintain compatibility with the old command structure
    
    # Sync command (journal sync)
    sync_parser = subparsers.add_parser('sync', help='Sync pages from Notion database')
    sync_parser.add_argument('--days', type=int, help='Number of days to look back for pages')
    sync_parser.add_argument('--database', type=str, help='Notion database ID')
    sync_parser.set_defaults(func=journal_sync)
    
    # List-sync command (notion list-sync)
    list_sync_parser = subparsers.add_parser('list-sync', help='List pages with Sync=true')
    list_sync_parser.add_argument('--database', type=str, help='Notion database ID')
    list_sync_parser.add_argument('--sync-property', type=str, help='Name of the sync property (default: "Sync")')
    list_sync_parser.set_defaults(func=notion_list_sync_pages)
    
    # Export-blog command (journal sync)
    export_blog_parser = subparsers.add_parser('export-blog', help='Export pages with Sync=true to markdown')
    export_blog_parser.add_argument('--database', type=str, help='Notion database ID')
    export_blog_parser.add_argument('--sync-property', type=str, help='Name of the sync property (default: "Sync")')
    export_blog_parser.set_defaults(func=journal_sync)
    
    # List-database command (notion properties)
    list_database_parser = subparsers.add_parser('list-database', help='List all properties in a Notion database')
    list_database_parser.add_argument('--database', type=str, help='Notion database ID')
    list_database_parser.set_defaults(func=notion_list_properties)
    
    # List-collection command (webflow fields)
    list_collection_parser = subparsers.add_parser('list-collection', help='List all fields in a Webflow collection')
    list_collection_parser.add_argument('--collection', type=str, help='Webflow collection ID')
    list_collection_parser.set_defaults(func=webflow_list_collection)
    
    # Debug-page command (notion debug)
    debug_page_parser = subparsers.add_parser('debug-page', help='Debug a specific Notion page')
    debug_page_parser.add_argument('--page-id', type=str, required=True, help='Notion page ID')
    debug_page_parser.set_defaults(func=notion_debug_page)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Execute the appropriate function
    if hasattr(args, 'func'):
        try:
            if asyncio.iscoroutinefunction(args.func):
                asyncio.run(args.func(args))
            else:
                args.func(args)
        except KeyboardInterrupt:
            print("\nOperation interrupted by user.")
        except Exception as e:
            print(f"Error: {str(e)}")
    else:
        # If no command was specified, print help
        if args.command == 'webflow' and not args.subcommand:
            # For webflow command with no subcommand, run the default function
            try:
                asyncio.run(webflow_command(args))
            except Exception as e:
                print(f"Error: {str(e)}")
        else:
            parser.print_help()

if __name__ == "__main__":
    main() 