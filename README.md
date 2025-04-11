# Maia

A modular Python framework for Notion integration and automation, with features for syncing Notion pages to markdown and integrating with various platforms.

## Features

- **Modular Architecture**: Clean, maintainable code structure
- **Notion Integration**: Sync pages from Notion databases to markdown
- **Blog Export**: Export pages marked for sync to your blog
- **Webflow CMS Integration**: Directly sync Notion content to Webflow CMS
- **CLI Interface**: Intuitive command-line interface
- **Extensible Design**: Easy to add new integrations and features

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/maia
cd maia

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .
```

### Using pip

```bash
pip install maia
```

## Configuration

Create a `.env` file in your project directory with the following variables:

```
# Notion API configuration
NOTION_TOKEN=your_notion_integration_token
NOTION_DATABASE_ID=your_default_database_id

# Webflow API configuration (if using the Webflow integration)
WEBFLOW_API_KEY=your_webflow_api_key
WEBFLOW_SITE_ID=your_webflow_site_id
WEBFLOW_COLLECTION_ID=your_webflow_collection_id
```

## Usage

Maia provides a command-line interface with several commands:

### Sync Notion Pages

Sync pages from a Notion database:

```bash
maia sync --days 10 --database your_database_id
```

This will:

- Fetch pages from the last 10 days
- Convert them to markdown
- Save them in the `notion-pages` directory

### List Pages with Sync Flag

List all pages in a specific database that have their "Sync" property checked:

```bash
maia list-sync
```

### Export Blog Pages

Export pages with "Sync" property checked to markdown:

```bash
maia export-blog
```

### Sync to Webflow CMS

Sync Notion pages to your Webflow CMS collection:

```bash
maia webflow --database your_notion_database_id --collection your_webflow_collection_id
```

This will:

- Get all pages from Notion with the "Sync" property checked
- Convert Notion blocks directly to HTML (no markdown intermediate)
- Create or update items in your Webflow CMS collection
- Publish items if the "Publish" property is checked

## Project Structure

```
maia/
├── maia/                   # Main package
│   ├── __init__.py         # Package initialization
│   ├── cli.py              # Command-line interface
│   ├── notion/             # Notion API interaction
│   │   ├── client.py       # Client setup
│   │   └── pages.py        # Page operations
│   ├── markdown/           # Markdown processing
│   │   └── converter.py    # Block to markdown conversion
│   ├── html/               # HTML processing
│   │   └── converter.py    # Block to HTML conversion
│   ├── webflow/            # Webflow integration
│   │   ├── client.py       # Webflow API client
│   │   └── sync.py         # Notion to Webflow sync
│   ├── storage/            # File operations
│   │   └── files.py        # File saving/loading
│   └── utils/              # Utilities
│       └── config.py       # Configuration management
├── setup.py                # Package setup script
├── requirements.txt        # Dependencies
└── README.md               # This file
```

## Development

### Adding New Features

To add new features to Maia:

1. Create a new module in the appropriate directory
2. Add your functionality with proper documentation
3. Update the CLI interface in `maia/cli.py`
4. Add tests in the `tests/` directory

### Running Tests

```bash
# To be implemented
pytest
```

## License

MIT

## Credits

Developed by Koii Benvenutto
