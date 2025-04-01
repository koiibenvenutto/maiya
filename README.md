# MAI from Scratch

A Python-based tool for syncing Notion pages to markdown and interacting with them through a terminal-based chat interface.

## Features

- Syncs Notion pages to markdown format
- Maintains a 60-day rolling window of pages
- Terminal-based chat interface with Claude
- Automatic cleanup of old pages
- Efficient handling of nested blocks
- Command history and auto-suggestions

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file with your Notion API token:
   ```
   NOTION_TOKEN=your_notion_integration_token
   ```

## Usage

### Syncing Notion Pages

To sync pages from your Notion database:

```bash
python get-notion-database.py
```

This will:

- Fetch pages from the last 60 days
- Convert them to markdown
- Save them in the `notion-pages` directory
- Clean up pages older than 60 days

### Chat Interface

To start the chat interface:

```bash
python chat.py
```

Available commands:

- `exit`: Exit the chat
- `clear`: Clear the chat history
- `help`: Show available commands
- `sync`: Sync latest pages from Notion

## Project Structure

- `get-notion-database.py`: Main script for syncing Notion pages
- `chat.py`: Terminal-based chat interface
- `notion-pages/`: Directory containing markdown files
- `.env`: Environment variables (not tracked in git)
- `last_sync.json`: Tracks last successful sync time

## Notes

- The script skips image blocks as they won't be accessible to AI models
- Pages are automatically cleaned up after 60 days
- Chat history is saved in `.chat_history`
