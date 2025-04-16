"""
File storage operations for saving and reading markdown files.
"""
import os
import glob
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Default output directory
OUTPUT_DIR = "notion-pages"

def ensure_output_dir():
    """Ensure the output directory exists."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

async def save_page_to_file(page_id: str, title: str, markdown_content: str) -> str:
    """
    Save a page to a markdown file.
    
    Args:
        page_id: ID of the page
        title: Title of the page
        markdown_content: Markdown content to save
        
    Returns:
        Path to the saved file
    """
    ensure_output_dir()
    
    # Create a safe filename from the title
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    
    # Create the filename with just the title and page ID
    filename = f"{safe_title} {page_id}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # Save the markdown content to the file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    return filepath

def get_existing_page_ids() -> set:
    """
    Get the IDs of existing saved pages.
    
    Returns:
        Set of page IDs that have already been saved
    """
    existing_ids = set()
    for file in glob.glob(os.path.join(OUTPUT_DIR, "*.md")):
        # Extract page ID from filename (last part after the last space)
        try:
            page_id = file.split()[-1].replace('.md', '')
            existing_ids.add(page_id)
        except:
            # Skip files with invalid format
            pass
    return existing_ids

def cleanup_old_pages(days: int = 30) -> int:
    """
    This function previously removed markdown files older than the specified 
    number of days, but we're now disabling this behavior to prevent unwanted
    file deletion. The files will remain in the OUTPUT_DIR.
    
    Args:
        days: Number of days parameter (ignored)
        
    Returns:
        Always returns 0 (no files removed)
    """
    # We no longer remove older files
    return 0

def read_markdown_files(days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read markdown files and return their content as a list of dictionaries.
    
    Args:
        days: Optional number of days to look back (based on file modification time, not filename)
        
    Returns:
        List of dictionaries with file data
    """
    ensure_output_dir()
    
    pages = []
    markdown_files = glob.glob(os.path.join(OUTPUT_DIR, "*.md"))
    
    for file_path in markdown_files:
        try:
            # Use file modification time as the date
            file_mtime = os.path.getmtime(file_path)
            date_obj = datetime.fromtimestamp(file_mtime)
            date_str = date_obj.strftime("%Y-%m-%d")
            
            # Filter by days if specified
            if days is not None:
                cutoff_date = datetime.now() - timedelta(days=days)
                if date_obj < cutoff_date:
                    continue
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract filename
            filename = os.path.basename(file_path)
            
            # Add to pages list
            pages.append({
                'date': date_str,
                'date_obj': date_obj,
                'content': content,
                'file_path': file_path,
                'filename': filename
            })
            
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
    
    # Sort by date, newest first
    pages.sort(key=lambda x: x['date_obj'], reverse=True)
    
    return pages 