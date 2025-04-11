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
    
    # Get the current date for the filename
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Create a safe filename from the title
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    
    # Create the filename with the date, title, and page ID
    filename = f"{date_str} {safe_title} {page_id}.md"
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
    Remove markdown files older than the specified number of days.
    
    Args:
        days: Number of days to keep files for
        
    Returns:
        Number of files removed
    """
    days_ago = datetime.now() - timedelta(days=days)
    
    removed_count = 0
    for file in os.listdir(OUTPUT_DIR):
        if file.endswith('.md'):
            filepath = os.path.join(OUTPUT_DIR, file)
            # Get file modification time
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < days_ago:
                try:
                    os.remove(filepath)
                    removed_count += 1
                    print(f"Removed old file: {file}")
                except Exception as e:
                    print(f"Error removing {file}: {str(e)}")
    
    return removed_count

def read_markdown_files(days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read markdown files and return their content as a list of dictionaries.
    
    Args:
        days: Optional number of days to look back
        
    Returns:
        List of dictionaries with file data
    """
    ensure_output_dir()
    
    pages = []
    markdown_files = glob.glob(os.path.join(OUTPUT_DIR, "*.md"))
    
    for file_path in markdown_files:
        try:
            # Extract date from filename (assuming format "YYYY-MM-DD Title PageID.md")
            filename = os.path.basename(file_path)
            date_str = filename.split(" ")[0]
            
            # Skip files that don't match our date format
            if not date_str or len(date_str) != 10:
                continue
                
            # Parse the date
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
                
            # Filter by days if specified
            if days is not None:
                cutoff_date = datetime.now() - timedelta(days=days)
                if date_obj < cutoff_date:
                    continue
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to pages list
            pages.append({
                'date': date_str,
                'date_obj': date_obj,
                'content': content,
                'file_path': file_path
            })
            
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
    
    # Sort by date, newest first
    pages.sort(key=lambda x: x['date_obj'], reverse=True)
    
    return pages 