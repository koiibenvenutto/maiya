"""
Terminal-based chat interface for interacting with AI models.
"""
from anthropic import Anthropic
from openai import OpenAI
import os
import glob
import sys
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
import asyncio
import traceback  # Added for detailed error tracing

from maia.storage.files import read_markdown_files
from maia.utils.config import get_chat_days_setting, set_chat_days_setting, get_sync_days_setting, set_sync_days_setting
from maia.notion.pages import get_pages_by_date

# Configuration file for API preferences
API_PREFERENCE_FILE = os.path.join(os.path.expanduser("~"), ".maia_api_preference")

# Function to get saved API preference
def get_api_preference():
    """Get the saved API preference."""
    try:
        if os.path.exists(API_PREFERENCE_FILE):
            with open(API_PREFERENCE_FILE, 'r') as f:
                api_type = f.read().strip()
                if api_type in ["anthropic", "openai"]:
                    return api_type
    except Exception as e:
        debug_print(f"Error reading API preference: {str(e)}")
    
    return "anthropic"  # Default to anthropic if no valid preference found

# Function to save API preference
def save_api_preference(api_type):
    """Save the API preference."""
    try:
        with open(API_PREFERENCE_FILE, 'w') as f:
            f.write(api_type)
        debug_print(f"API preference saved: {api_type}")
        return True
    except Exception as e:
        debug_print(f"Error saving API preference: {str(e)}")
        return False

# Initialize API clients if API keys are available
anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global variable to track which API is being used - now reads from saved preference
current_api = get_api_preference()
os.environ["API_TYPE"] = current_api  # Ensure environment variable matches saved preference

# Initialize Rich console with a custom theme
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "user": "green",
    "assistant": "white",
    "debug": "magenta",  # Added for debug messages
})
console = Console(theme=custom_theme)  # Use default terminal width

# Debug mode flag
DEBUG_MODE = os.getenv("MAIA_DEBUG", "0") == "1"

# Create a session for the prompt
session = PromptSession(history=FileHistory('.chat_history'))

# Define styles
style = Style.from_dict({
    'prompt': 'ansicyan bold',
    'input': 'ansiwhite',
    'assistant': 'ansigreen',
    'user': 'ansiblue',
})

def debug_print(message):
    """Print debug messages if debug mode is enabled."""
    if DEBUG_MODE:
        console.print(f"[debug]{message}[/debug]")

def load_prompt_templates():
    """Load prompt templates from prompt.md file."""
    try:
        with open('prompt.md', 'r') as f:
            prompt_md_content = f.read()
        
        # Extract system prompts and project instructions from the markdown content
        # Assuming the markdown file is structured with headings, we can split by sections
        sections = prompt_md_content.split('\n## ')
        
        # Extract the system prompt section
        system_prompt_section = next((s for s in sections if s.startswith('System Prompt')), '')
        
        # Extract the project instructions section
        project_instructions_section = next((s for s in sections if s.startswith('Project Purpose')), '')
        
        return {
            "system_prompt": system_prompt_section,
            "project_instructions": project_instructions_section
        }
    except Exception as e:
        console.print(f"[error]Error loading prompt templates: {str(e)}[/error]")
        return {
            "system_prompt": "You are a helpful assistant.",
            "project_instructions": ""
        }

def create_system_prompt(pages, for_api="anthropic"):
    """
    Create a system prompt that includes the content of markdown files.
    Limits content based on API to prevent token limit issues.
    
    Args:
        pages: List of page data
        for_api: Which API to format for ("anthropic" or "openai")
        
    Returns:
        Formatted system prompt
    """
    # Get prompt templates
    templates = load_prompt_templates()
    system_prompt_template = templates["system_prompt"]
    
    # Get today's date
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    # Get days setting
    last_days = get_chat_days_setting()
    debug_print(f"Using chat context days setting: {last_days}")
    
    # Calculate the date 'last_days' ago
    days_ago = today - timedelta(days=last_days)
    debug_print(f"Including entries from {days_ago.strftime('%Y-%m-%d')} onward")
    
    # Filter pages by date
    date_filtered_pages = []
    for page in pages:
        page_date = page.get('date_obj')
        if page_date and page_date >= days_ago:
            date_filtered_pages.append(page)
            debug_print(f"Date match: {page.get('date', 'Unknown')} (obj: {page_date})")
        elif page_date:
            debug_print(f"Date excluded: {page.get('date', 'Unknown')} (obj: {page_date})")
    
    debug_print(f"Filtered journal entries from {len(pages)} to {len(date_filtered_pages)} entries within {last_days} days")
    
    # Sort pages by date, newest first
    sorted_pages = sorted(date_filtered_pages, key=lambda x: x.get('date_obj', datetime.now()), reverse=True)
    
    base_prompt = system_prompt_template.format(today=today_str)
    
    if for_api == "anthropic":
        # Use all date-filtered pages for Claude (no additional limits)
        for page in sorted_pages:
            base_prompt += f"Entry from {page['date']}:\n{page['content']}\n\n"
            debug_print(f"Added entry from {page['date']} to context")
    else:  # OpenAI has more limited context
        # For OpenAI, we'll still limit to the most recent entries, but ONLY from within the filtered date range
        max_entries = min(5, len(sorted_pages))  # Use at most 5 entries
        debug_print(f"Adding {max_entries} most recent entries for OpenAI (within {last_days} days)")
        
        for i, page in enumerate(sorted_pages[:max_entries]):
            # Further truncate content if needed
            content = page['content']
            if len(content) > 2000:  # Arbitrary limit to prevent token overflows
                content = content[:2000] + "... (content truncated)"
            base_prompt += f"Entry from {page['date']}:\n{content}\n\n"
            debug_print(f"Added entry #{i+1}: {page['date']} to context (OpenAI)")
    
    base_prompt += f"\nRemember: Today is {today_str}. Always reference the correct dates from the filenames when discussing entries."
    return base_prompt

def format_message(role, content):
    """Format a message with markdown support."""
    return Markdown(content)

def print_welcome_message():
    """Print welcome message with available commands."""
    console.print(Panel.fit(
        "[bold cyan]Welcome to the Maia Chat Interface![/bold cyan]\n\n"
        "[bold]Available Commands:[/bold]\n"
        "- [green]exit[/green]: Exit the chat\n"
        "- [green]clear[/green]: Clear chat history\n"
        "- [green]help[/green]: Show this help message\n"
        "- [green]sync[/green]: Sync Notion pages\n"
        "- [green]days[/green]: Set the number of days of journal entries to include\n"
        "- [green]debug[/green]: Toggle debug mode\n"
        f"- [green]switch[/green]: Switch between Anthropic and OpenAI (currently using {current_api})",
        title="Maia Chat",
        border_style="cyan",
        width=80
    ))

def switch_api():
    """
    Switch between Anthropic and OpenAI APIs.
    
    Returns:
        New API name
    """
    global current_api
    
    debug_print(f"Switching API from {current_api}")
    
    if current_api == "anthropic":
        if not os.getenv("OPENAI_API_KEY"):
            console.print("[error]OpenAI API key not found. Please set OPENAI_API_KEY environment variable.[/error]")
            console.print("[info]Staying with Anthropic API[/info]")
            return current_api
            
        current_api = "openai"
        os.environ["API_TYPE"] = "openai"
        # Save preference to file for persistence between sessions
        save_api_preference(current_api)
        console.print("[info]Switched to OpenAI[/info]")
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[error]Anthropic API key not found. Please set ANTHROPIC_API_KEY environment variable.[/error]")
            console.print("[info]Staying with OpenAI API[/info]")
            return current_api
            
        current_api = "anthropic"
        os.environ["API_TYPE"] = "anthropic"
        # Save preference to file for persistence between sessions
        save_api_preference(current_api)
        console.print("[info]Switched to Anthropic[/info]")
    
    debug_print(f"New API: {current_api}")
    return current_api

def set_days():
    """
    Set the number of days of journal entries to include in context.
    
    Returns:
        Integer representing the new setting
    """
    try:
        current_days = get_chat_days_setting()
        console.print(f"[info]Current chat context days setting: {current_days} days[/info]")
        
        # Get user input for new value
        days_str = input("Enter number of days of journal entries to include in chat context (or press Enter to keep current): ")
        
        if not days_str.strip():
            console.print(f"[info]Keeping current setting: {current_days} days[/info]")
            return current_days
        
        try:
            days = int(days_str)
            if days < 1:
                console.print("[warning]Days must be at least 1. Setting to 1.[/warning]")
                days = 1
                
            # Update the setting
            set_chat_days_setting(days)
            console.print(f"[info]Updated chat context days setting: {days} days[/info]")
            
            debug_print(f"Chat context days setting updated from {current_days} to {days}")
            return days
            
        except ValueError:
            console.print("[error]Invalid input. Please enter a number.[/error]")
            return current_days
            
    except Exception as e:
        console.print(f"[error]Error setting days: {str(e)}[/error]")
        debug_print(f"Exception in set_days: {traceback.format_exc()}")
        return get_chat_days_setting()  # Fall back to current setting

def chat():
    """Main chat loop with markdown support."""
    global DEBUG_MODE
    
    # Load journal entries
    pages = read_markdown_files()
    console.print(f"[info]Loaded {len(pages)} journal entries[/info]")
    debug_print(f"Pages loaded: {', '.join([p.get('date', 'Unknown') for p in pages[:5]])}...")

    # Create the system prompts for both APIs
    anthropic_system_prompt = create_system_prompt(pages, "anthropic")
    openai_system_prompt = create_system_prompt(pages, "openai")
    
    debug_print(f"Anthropic system prompt length: {len(anthropic_system_prompt)} chars")
    debug_print(f"OpenAI system prompt length: {len(openai_system_prompt)} chars")

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
            elif user_input.lower() == 'debug':
                DEBUG_MODE = not DEBUG_MODE
                os.environ["MAIA_DEBUG"] = "1" if DEBUG_MODE else "0"
                console.print(f"[info]Debug mode {'enabled' if DEBUG_MODE else 'disabled'}[/info]")
                continue
            elif user_input.lower() == 'sync':
                debug_print("Running sync command")
                console.print("[info]Starting sync process...[/info]")
                
                # Get the default days value
                days_value = get_sync_days_setting() or 7
                
                # Prompt user for days
                days_input = input(f"Enter number of days to sync (default: {days_value}): ").strip()
                
                # If user entered a value, use it; otherwise use the default
                if days_input:
                    try:
                        days_value = int(days_input)
                        if days_value < 1:
                            console.print("[warning]Days must be at least 1. Setting to 1.[/warning]")
                            days_value = 1
                        # Update the setting for next time
                        set_sync_days_setting(days_value)
                    except ValueError:
                        console.print(f"[warning]Invalid input. Using default ({days_value} days).[/warning]")
                
                # Run the sync process in a way that preserves all console output
                import subprocess
                import sys
                
                try:
                    # Use python -m directly instead of the bash script
                    cmd = ["python", "-m", "maia", "journal", str(days_value)]
                    debug_print(f"Running command: {' '.join(cmd)}")
                    
                    # Use subprocess.run with live output
                    process = subprocess.run(
                        " ".join(cmd),
                        check=False,  # Don't raise an exception if return code is non-zero
                        text=True,
                        shell=True,  # Execute through shell to ensure proper environment
                        stdout=None,  # Use default stdout (terminal)
                        stderr=None   # Use default stderr (terminal)
                    )
                    
                    # Check return code
                    if process.returncode != 0:
                        console.print(f"[error]Sync process returned error code: {process.returncode}[/error]")
                    else:
                        console.print("[info]Sync completed successfully[/info]")
                    
                    # Reload pages regardless of return code
                    pages = read_markdown_files()
                    anthropic_system_prompt = create_system_prompt(pages, "anthropic")
                    openai_system_prompt = create_system_prompt(pages, "openai")
                    
                    # Clear chat history to avoid confusion with potentially new/changed content
                    messages = []
                    
                    console.print("[info]Chat context updated with journal entries[/info]")
                    debug_print(f"Loaded {len(pages)} journal entries after sync")
                    
                except Exception as e:
                    console.print(f"[error]Error running sync command: {str(e)}[/error]")
                    debug_print(f"Exception details: {traceback.format_exc()}")
                
                continue
            elif user_input.lower() == 'switch':
                debug_print("Running switch command")
                switch_api()
                # Clear messages when switching to prevent context overflow
                messages = []
                console.print("[info]Chat history cleared due to API switch[/info]")
                print_welcome_message()
                continue
            elif user_input.lower() == 'days':
                debug_print("Running days command")
                
                old_days = get_chat_days_setting()
                new_days = set_days()
                
                # Reload pages to ensure we have all available entries
                pages = read_markdown_files()
                debug_print(f"Reloaded {len(pages)} journal entries")
                
                # Update system prompts with new days setting
                anthropic_system_prompt = create_system_prompt(pages, "anthropic")
                openai_system_prompt = create_system_prompt(pages, "openai")
                
                # Always clear messages when changing days setting
                messages = []
                
                if old_days != new_days:
                    debug_print(f"Days setting changed from {old_days} to {new_days}")
                    console.print("[info]Context updated with new days setting. Chat history cleared.[/info]")
                else:
                    console.print("[info]Days setting unchanged. Chat history cleared.[/info]")
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})

            # Get response based on current API
            if current_api == "anthropic":
                if not anthropic_client:
                    console.print("[error]Anthropic API key not found. Please set ANTHROPIC_API_KEY.[/error]")
                    continue
                
                debug_print(f"Calling Anthropic API with {len(messages)} messages")
                try:
                    response = anthropic_client.messages.create(
                        model="claude-3-7-sonnet-20250219",
                        max_tokens=4096,
                        system=anthropic_system_prompt,
                        messages=messages,
                        temperature=0.7,
                    )
                    assistant_message = response.content[0].text
                    debug_print(f"Received response from Anthropic ({len(assistant_message)} chars)")
                except Exception as e:
                    error_details = traceback.format_exc()
                    console.print(f"[error]Error calling Anthropic API: {str(e)}[/error]")
                    debug_print(f"Anthropic API error details:\n{error_details}")
                    continue
            else:  # OpenAI
                if not openai_client:
                    console.print("[error]OpenAI API key not found. Please set OPENAI_API_KEY.[/error]")
                    continue
                
                debug_print(f"Calling OpenAI API with {len(messages)} messages")
                try:    
                    # Limit message history for OpenAI to last 10 messages to prevent context overflow
                    recent_messages = messages[-10:] if len(messages) > 10 else messages
                    debug_print(f"Using {len(recent_messages)} recent messages for OpenAI")
                    
                    response = openai_client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[{"role": "system", "content": openai_system_prompt}] + recent_messages,
                        temperature=0.7,
                    )
                    assistant_message = response.choices[0].message.content
                    debug_print(f"Received response from OpenAI ({len(assistant_message)} chars)")
                except Exception as e:
                    error_details = traceback.format_exc()
                    console.print(f"[error]Error calling OpenAI API: {str(e)}[/error]")
                    debug_print(f"OpenAI API error details:\n{error_details}")
                    continue

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})
            
            # Display a horizontal rule before the assistant message
            console.print("---")
            
            # Display assistant message with markdown formatting
            console.print(format_message("assistant", assistant_message))

            # Display a horizontal rule after the assistant message
            console.print("---")

        except KeyboardInterrupt:
            console.print("\n[info]Use 'exit' to quit[/info]")
            continue
        except Exception as e:
            error_details = traceback.format_exc()
            console.print(f"[error]Error: {str(e)}[/error]")
            debug_print(f"Exception details:\n{error_details}")
            continue

def main():
    """Entry point for the chat interface."""
    chat() 