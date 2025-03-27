from notion_client import Client
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


# Get your Notion token from the environment
notion_token = os.getenv("NOTION_TOKEN")

# Replace with your Notion integration token
notion = Client(auth=notion_token)

# Replace with your actual database ID
response = notion.databases.query(
    database_id="259700448ad145849e67fa1040a0e120", 
    filter={
        "property": "Date",
        "date": {
            "on_or_after": "2025-03-25"
        }   
    })

# Print the raw data for now
print(response)