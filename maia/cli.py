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
from maia.notion.pages import get_pages_by_date, get_page_title, get_block_content, clear_block_cache
from maia.markdown.converter import page_to_markdown
from maia.storage.files import save_page_to_file, get_existing_page_ids
from maia.utils.config import update_last_sync_time, get_last_sync_time, get_sync_days_setting, set_sync_days_setting

# Database IDs
WEBFLOW_CMS_DATABASE_ID = "10dd13396967807ab987c92a4d29b9b8"  # Database ID for Webflow CMS operations
JOURNAL_DATABASE_ID = os.getenv("NOTION_JOURNAL_DATABASE_ID", "259700448ad145849e67fa1040a0e120")  # Specific ID for journal database

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
    
    # Save the page to a file without adding today's date
    filepath = await save_page_to_file(page_id, title, markdown_content)
    
    print(f"[{index}/{total}] ✓ Saved page to {filepath}")
    print("-" * 80)

# ==================== JOURNAL COMMANDS ====================

async def journal_sync(args):
    """Sync journal entries from Notion to local markdown files."""
    print("Starting journal sync...")
    
    # Get database ID
    database_id = args.database or JOURNAL_DATABASE_ID
    if not database_id:
        raise ValueError("No database ID provided. Please specify with --database or set JOURNAL_DATABASE_ID environment variable.")
    
    print(f"Using database ID: {database_id}")
    
    # Get number of days
    if args.days is not None:
        days = args.days
        # Update the days setting
        set_sync_days_setting(days)
    else:
        days = get_sync_days_setting()
    
    print(f"Using days setting: {days}")
    
    # Get last sync time
    last_sync = get_last_sync_time()
    print(f"Last sync time: {last_sync or 'Never'}")
    
    # Get existing page IDs
    existing_page_ids = get_existing_page_ids()
    print(f"Found {len(existing_page_ids)} existing journal entries")
    
    print(f"\nSyncing journal entries from the last {days} days...")
    
    # Query the database for pages from the specified number of days
    try:
        pages = await get_pages_by_date(database_id, days)
        print(f"Successfully retrieved {len(pages)} pages from Notion")
    except Exception as e:
        print(f"Error retrieving pages from Notion: {str(e)}")
        raise
    
    # Filter pages based on last_edited_time and existing pages
    pages_to_sync = []
    skipped_count = 0
    
    for page in pages:
        page_id = page["id"]
        last_edited_time = page.get("last_edited_time")
        
        # Process pages that are either:
        # 1. New (not in existing_page_ids)
        # 2. Modified since last sync
        if page_id not in existing_page_ids:
            print(f"  Adding new page: {page_id}")
            pages_to_sync.append(page_id)
        elif not last_sync or (last_edited_time and last_edited_time > last_sync):
            print(f"  Adding modified page: {page_id} (edited: {last_edited_time})")
            pages_to_sync.append(page_id)
        else:
            skipped_count += 1
    
    print(f"Found {len(pages_to_sync)} journal entries to sync (skipped {skipped_count} unmodified entries)")
    
    # If no pages to sync, inform the user
    if not pages_to_sync:
        print("All journal entries are already up to date.")
        update_last_sync_time()
        print("\nJournal sync completed successfully!")
        return
    
    # Process pages sequentially to avoid memory issues
    for i, page_id in enumerate(pages_to_sync, 1):
        try:
            await process_page(page_id, i, len(pages_to_sync))
        except Exception as e:
            print(f"Error processing page {page_id}: {str(e)}")
            # Continue with the next page instead of failing completely
            continue
    
    # Update last sync time after successful sync
    update_last_sync_time()
    print("\nJournal sync completed successfully!")

# ==================== WEBFLOW COMMANDS ====================

async def webflow_sync(args):
    """Sync Notion pages to Webflow CMS."""
    # Import webflow sync module here to avoid circular imports
    from maia.webflow.sync import sync_to_webflow
    
    # Get database and collection IDs
    notion_database_id = args.database or WEBFLOW_CMS_DATABASE_ID
    webflow_collection_id = args.collection or os.getenv("WEBFLOW_COLLECTION_ID")
    sync_property = args.sync_property or "Sync"
    force_update = args.force if hasattr(args, 'force') else False
    
    print(f"Syncing Webflow CMS database {notion_database_id} to Webflow collection {webflow_collection_id}...")
    if force_update:
        print("Force update enabled - all items will be updated regardless of edit time")
    
    # Run the sync function
    return await sync_to_webflow(
        notion_database_id=notion_database_id, 
        webflow_collection_id=webflow_collection_id, 
        sync_property=sync_property,
        force_update=force_update
    )

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
    import sys
    
    # Check for direct 'maia journal X' pattern before parsing
    if len(sys.argv) >= 3 and sys.argv[1] == 'journal' and sys.argv[2].isdigit():
        days = int(sys.argv[2])
        print(f"Using shortcut: journal {days} (syncing last {days} days)")
        
        # Create args for journal_sync
        class Args:
            def __init__(self):
                self.days = days
                self.database = None
        
        # Run the journal sync with the days value
        asyncio.run(journal_sync(Args()))
        return
    
    # Regular command parsing for all other cases
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
    
    # Set default function for journal command when no subcommand is provided
    journal_parser.set_defaults(func=handle_journal_command)
    
    # ===== WEBFLOW COMMAND =====
    webflow_parser = subparsers.add_parser('webflow', help='Webflow commands')
    webflow_subparsers = webflow_parser.add_subparsers(dest='webflow_command', help='Webflow subcommands')
    
    # Sync command
    sync_parser = webflow_subparsers.add_parser('sync', help='Sync Notion pages to Webflow CMS')
    sync_parser.add_argument('--database', help='Notion database ID')
    sync_parser.add_argument('--collection', help='Webflow collection ID (default: WEBFLOW_COLLECTION_ID env var)')
    sync_parser.add_argument('--sync-property', help='Name of the sync property in Notion (default: "Sync")')
    sync_parser.add_argument('--force', action='store_true', help='Force update all items regardless of edit time')
    sync_parser.set_defaults(func=webflow_sync)
    
    # Fields command
    fields_parser = webflow_subparsers.add_parser('fields', help='List all fields in a Webflow collection')
    fields_parser.add_argument('--collection', required=True, help='Webflow collection ID')
    fields_parser.set_defaults(func=webflow_list_collection)
    
    # ===== CHAT COMMAND =====
    chat_parser = subparsers.add_parser('chat', help='Start the chat interface')
    chat_parser.set_defaults(func=chat_run)
    
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
        if args.command == 'webflow' and not args.webflow_command:
            # For webflow command with no subcommand, run the default function
            try:
                asyncio.run(webflow_command(args))
            except Exception as e:
                print(f"Error: {str(e)}")
        elif args.command == 'journal' and not args.subcommand:
            # For journal command with no subcommand, run the default handler
            try:
                asyncio.run(handle_journal_command(args))
            except Exception as e:
                print(f"Error: {str(e)}")
        else:
            parser.print_help()

# Add handler for direct journal command with days argument
async def handle_journal_command(args):
    """Handle journal command when called with no arguments."""
    # Show help for journal command
    print("Journal command usage examples:")
    print("  maia journal 7         # Sync the last 7 days")
    print("  maia journal sync      # Sync using the default days setting")
    print("  maia journal sync --days 14  # Sync the last 14 days")

if __name__ == "__main__":
    main() 