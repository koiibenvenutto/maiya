from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv
import os
import glob
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.theme import Theme
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Initialize API clients
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global variable to track which API is being used
current_api = "anthropic"

# Initialize Rich console with a custom theme and width limit
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "user": "green",
    "assistant": "magenta",
})
console = Console(theme=custom_theme, width=80)  # Set max width to 80 characters

# Create a session for the prompt
session = PromptSession(history=FileHistory('.chat_history'))

# Define styles
style = Style.from_dict({
    'prompt': 'ansicyan bold',
    'input': 'ansiwhite',
    'assistant': 'magenta',
    'user': 'ansigreen',
})

def read_markdown_files(directory="notion-pages"):
    """Read all markdown files from the specified directory."""
    pages = []
    if os.path.exists(directory):
        for file in glob.glob(os.path.join(directory, "*.md")):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    filename = os.path.basename(file)
                    
                    # Extract date from filename (format: YYYY-MM-DD-HHMM-SS page_id.md)
                    date_str = None
                    try:
                        # Extract the date part (YYYY-MM-DD-HHMM-SS)
                        date_part = filename.split()[0]
                        # Parse the date
                        date_str = date_part
                        # Convert to datetime for sorting
                        date_obj = datetime.strptime(date_part, "%Y-%m-%d-%H%M-%S")
                    except (ValueError, IndexError):
                        # If date extraction fails, use file modification time
                        date_obj = datetime.fromtimestamp(os.path.getmtime(file))
                        date_str = date_obj.strftime("%Y-%m-%d")
                    
                    pages.append({
                        "filename": filename,
                        "content": content,
                        "date": date_str,
                        "date_obj": date_obj
                    })
            except Exception as e:
                console.print(f"[error]Error reading {file}: {str(e)}[/error]")
    
    # Sort pages by date (newest first)
    pages.sort(key=lambda x: x["date_obj"], reverse=True)
    
    return pages

# Load the prompt configuration from prompt.md
with open('prompt.md', 'r') as f:
    prompt_md_content = f.read()

# Extract system prompts and project instructions from the markdown content
# Assuming the markdown file is structured with headings, we can split by sections
sections = prompt_md_content.split('\n## ')

# Extract the system prompt section
system_prompt_section = next((s for s in sections if s.startswith('System Prompt')), '')

# Extract the project instructions section
project_instructions_section = next((s for s in sections if s.startswith('Project Purpose')), '')

# Use the system prompt section for both Anthropic and OpenAI
anthropic_system_prompt_template = system_prompt_section
openai_system_prompt_template = system_prompt_section

# Use the project instructions section
project_instructions = project_instructions_section

def create_system_prompt(pages, for_api="anthropic"):
    """Create a system prompt that includes the content of markdown files.
    Limits content based on API to prevent token limit issues."""
    # Get today's date
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    # Calculate the date 5 days ago
    five_days_ago = today - timedelta(days=5)
    
    # Filter pages to include only those from the last 5 days
    recent_pages = [page for page in pages if page['date_obj'] >= five_days_ago]
    
    if for_api == "anthropic":
        base_prompt = anthropic_system_prompt_template.format(today=today_str)
        # Use filtered pages for Claude's context window
        for page in recent_pages:
            base_prompt += f"Entry from {page['date']}:\n{page['content']}\n\n"
    else:  # OpenAI has more limited context
        base_prompt = openai_system_prompt_template.format(today=today_str)
        # Use filtered pages for OpenAI's context window
        for page in recent_pages[:5]:  # Limit to the most recent 5 entries
            # Further truncate content if needed
            content = page['content']
            if len(content) > 2000:  # Arbitrary limit to prevent token overflows
                content = content[:2000] + "... (content truncated)"
            base_prompt += f"Entry from {page['date']}:\n{content}\n\n"
    
    base_prompt += f"\nRemember: Today is {today_str}. Always reference the correct dates from the filenames when discussing entries."
    return base_prompt

def format_message(role, content):
    """Format a message with markdown support and color coding."""
    if role == "user":
        console.rule()
    else:
        console.print(f"[white]{content}[/white]")
        console.rule()

def print_welcome_message():
    """Print welcome message with available commands."""
    console.print(Panel.fit(
        "[bold cyan]Welcome to the Chat Interface![/bold cyan]\n\n"
        "[bold]Available Commands:[/bold]\n"
        "- [green]exit[/green]: Exit the chat\n"
        "- [green]clear[/green]: Clear chat history\n"
        "- [green]help[/green]: Show this help message\n"
        "- [green]sync[/green]: Sync Notion pages\n"
        f"- [green]switch[/green]: Switch between Anthropic and OpenAI (currently using {current_api})",
        title="Help",
        border_style="cyan",
        width=80
    ))

def switch_api():
    """Switch between Anthropic and OpenAI APIs and set the API_TYPE environment variable."""
    global current_api
    if current_api == "anthropic":
        current_api = "openai"
        os.environ["API_TYPE"] = "openai"
        console.print("[info]Switched to OpenAI[/info]")
    else:
        current_api = "anthropic"
        os.environ["API_TYPE"] = "anthropic"
        console.print("[info]Switched to Anthropic[/info]")

def sync_notion_pages():
    """Sync pages from Notion."""
    try:
        import subprocess
        import json
        import os
        
        # Get the last used number of days from the sync_config.json file
        config_file = "sync_config.json"
        last_days = 1  # Default to 1 day if no config exists
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    last_days = config.get('last_days', 1)
            except Exception:
                pass
        
        # Ask the user for the number of days
        console.print("[info]How many days back would you like to sync?[/info]")
        console.print(f"[info]Press Enter to use the last value ({last_days} days) or type a number.[/info]")
        
        user_input = session.prompt(HTML('<style fg="green">Days: </style>')).strip()
        
        # Use the user input or default to the last used value
        if user_input:
            try:
                days = int(user_input)
                if days <= 0:
                    console.print("[warning]Invalid input. Using default value.[/warning]")
                    days = last_days
            except ValueError:
                console.print("[warning]Invalid input. Using default value.[/warning]")
                days = last_days
        else:
            days = last_days
        
        # Save the new value to the sync_config.json file
        # First read the existing file to preserve other settings
        config_data = {}
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
            except Exception:
                pass
        
        # Update the last_days value
        config_data['last_days'] = days
        
        # Write the updated config back to the file
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        console.print(f"[info]Syncing pages from the last {days} days...[/info]")
        
        # Run the sync script with the days parameter
        result = subprocess.run(['python', 'get-notion-database.py', '--days', str(days)], 
                              capture_output=True, 
                              text=True)
        
        if result.returncode == 0:
            console.print("[info]Sync completed successfully![/info]")
            return True
        else:
            console.print(f"[error]Error during sync: {result.stderr}[/error]")
            return False
    except Exception as e:
        console.print(f"[error]Error running sync: {str(e)}[/error]")
        return False

def chat():
    """Main chat loop with markdown support."""
    # Load journal entries
    pages = read_markdown_files()
    console.print(f"[info]Loaded {len(pages)} journal entries[/info]")

    # Create the system prompts for both APIs
    anthropic_system_prompt = create_system_prompt(pages, "anthropic")
    openai_system_prompt = create_system_prompt(pages, "openai")

    # Print welcome message
    print_welcome_message()

    # Initialize conversation history (without system message)
    messages = []

    while True:
        try:
            # Get user input
            user_input = session.prompt(HTML('<style fg="green">You: </style>')).strip()

            # Handle commands
            if user_input.lower() == 'exit':
                console.print("[info]Goodbye![/info]")
                break
            elif user_input.lower() == 'clear':
                messages = []
                console.print("[info]Chat history cleared[/info]")
                continue
            elif user_input.lower() == 'help':
                print_welcome_message()
                continue
            elif user_input.lower() == 'sync':
                if sync_notion_pages():
                    # Reload pages and update system prompts
                    pages = read_markdown_files()
                    anthropic_system_prompt = create_system_prompt(pages, "anthropic")
                    openai_system_prompt = create_system_prompt(pages, "openai")
                    messages = []
                    console.print("[info]Chat context updated with new pages[/info]")
                continue
            elif user_input.lower() == 'switch':
                switch_api()
                # Clear messages when switching to prevent context overflow
                messages = []
                console.print("[info]Chat history cleared due to API switch[/info]")
                print_welcome_message()
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})

            # Display user message with markdown formatting and color coding
            format_message("user", user_input)

            # Get response based on current API
            if current_api == "anthropic":
                response = anthropic_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=4096,
                    system=anthropic_system_prompt,
                    messages=messages,
                    temperature=0.7,
                )
                assistant_message = response.content[0].text
            else:  # OpenAI
                # Limit message history for OpenAI to last 5 messages to prevent context overflow
                recent_messages = messages[-10:] if len(messages) > 10 else messages
                response = openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "system", "content": openai_system_prompt}] + recent_messages,
                    temperature=0.7,
                )
                assistant_message = response.choices[0].message.content

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})
            
            # Display assistant message with markdown formatting and color coding
            format_message("assistant", assistant_message)

        except KeyboardInterrupt:
            console.print("\n[info]Use 'exit' to quit[/info]")
            continue
        except Exception as e:
            console.print(f"[error]Error: {str(e)}[/error]")
            continue

if __name__ == "__main__":
    chat() 