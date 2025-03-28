from anthropic import Anthropic
from dotenv import load_dotenv
import os
import glob
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def read_markdown_files(directory="notion-pages"):
    """Read all markdown files from the specified directory."""
    markdown_files = glob.glob(os.path.join(directory, "*.md"))
    pages = []
    
    for file_path in markdown_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract page ID from filename (last part before .md)
            page_id = os.path.splitext(os.path.basename(file_path))[0].split()[-1]
            pages.append({
                'id': page_id,
                'content': content,
                'filename': os.path.basename(file_path),
                'file_path': file_path
            })
    
    return pages

def create_claude_project(name=None):
    """Create a new Claude project."""
    if name is None:
        name = "koiib-2025-03-28-0022-09"
    
    try:
        # Create a new project
        response = client.projects.create(
            name=name,
            description="My Notion Journal Entries"
        )
        return response.id
    except Exception as e:
        print(f"Error creating project: {str(e)}")
        return None

def add_pages_to_project(project_id, pages):
    """Add pages to the Claude project's knowledge base."""
    for page in pages:
        try:
            # Upload the file to the project's knowledge base
            with open(page['file_path'], 'rb') as f:
                file_content = f.read()
                
            response = client.files.create(
                file=file_content,
                metadata={
                    "name": page['filename'],
                    "description": f"Notion journal entry from {page['filename']}"
                }
            )
            
            # Add the file to the project's knowledge base
            client.projects.files.create(
                project_id=project_id,
                file_id=response.id
            )
            
            print(f"Added page {page['filename']} to project knowledge base")
        except Exception as e:
            print(f"Error adding page {page['filename']}: {str(e)}")

def save_project_id(project_id):
    """Save the project ID to a file for future use."""
    with open('claude_project_id.txt', 'w') as f:
        f.write(project_id)
    print(f"Saved project ID to claude_project_id.txt")

def load_project_id():
    """Load the project ID from file if it exists."""
    try:
        with open('claude_project_id.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def main():
    # Read markdown files
    print("Reading markdown files...")
    pages = read_markdown_files()
    print(f"Found {len(pages)} pages")
    
    # Check for existing project ID
    project_id = load_project_id()
    
    if not project_id:
        # Create new project
        print("\nCreating new Claude project...")
        project_id = create_claude_project()
        if not project_id:
            print("Failed to create project")
            return
        
        print(f"Created project with ID: {project_id}")
        save_project_id(project_id)
    else:
        print(f"\nUsing existing project with ID: {project_id}")
    
    # Add pages to project
    print("\nAdding pages to project knowledge base...")
    add_pages_to_project(project_id, pages)
    print("\nDone!")

if __name__ == "__main__":
    main() 