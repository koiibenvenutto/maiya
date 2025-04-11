"""
Notion API client initialization and configuration.
"""
from notion_client import AsyncClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_client():
    """Initialize and return an async Notion client."""
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable not found. Please add it to your .env file.")
    
    return AsyncClient(auth=notion_token)

# Initialize client on module import
notion_client = get_client() 