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
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize API clients
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Global variable to track which API is being used
current_api = "anthropic"

# Initialize Rich console with a custom theme
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "user": "green",
    "assistant": "blue",
})
console = Console(theme=custom_theme)

# Create a session for the prompt
session = PromptSession(history=FileHistory('.chat_history'))

# Define styles
style = Style.from_dict({
    'prompt': 'ansicyan bold',
    'input': 'ansiwhite',
    'assistant': 'ansigreen',
    'user': 'ansiblue',
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
                    pages.append({"filename": filename, "content": content})
            except Exception as e:
                console.print(f"[error]Error reading {file}: {str(e)}[/error]")
    return pages

def create_system_prompt(pages):
    """Create a system prompt that includes the content of markdown files."""
    base_prompt = "You are Claude, an AI assistant. You have access to the following journal entries:\n\n"
    for page in pages:
        base_prompt += f"File: {page['filename']}\n{page['content']}\n\n"
    base_prompt += "\nPlease use this information to help answer questions. If you reference any specific entries, mention them by name."
    return base_prompt

def format_message(role, content):
    """Format a message with markdown support."""
    if role == "user":
        return Panel(Markdown(content), style="green", title="You")
    else:
        return Panel(Markdown(content), style="blue", title="Claude")

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
        border_style="cyan"
    ))

def switch_api():
    """Switch between Anthropic and OpenAI APIs."""
    global current_api
    if current_api == "anthropic":
        current_api = "openai"
        console.print("[info]Switched to OpenAI[/info]")
    else:
        current_api = "anthropic"
        console.print("[info]Switched to Anthropic[/info]")

def sync_notion_pages():
    """Sync pages from Notion."""
    try:
        import subprocess
        console.print("[info]Syncing pages from Notion...[/info]")
        result = subprocess.run(['python', 'get-notion-database.py'], 
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

    # Create the system prompt
    system_prompt = create_system_prompt(pages)

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
                    # Reload pages and update system prompt
                    pages = read_markdown_files()
                    system_prompt = create_system_prompt(pages)
                    messages = []
                    console.print("[info]Chat context updated with new pages[/info]")
                continue
            elif user_input.lower() == 'switch':
                switch_api()
                print_welcome_message()
                continue

            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            # Display user message with markdown formatting
            console.print(format_message("user", user_input))

            # Get response based on current API
            if current_api == "anthropic":
                response = anthropic_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    temperature=0.7,
                )
                assistant_message = response.content[0].text
            else:  # OpenAI
                response = openai_client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    temperature=0.7,
                )
                assistant_message = response.choices[0].message.content

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})
            
            # Display assistant message with markdown formatting
            console.print(format_message("assistant", assistant_message))

        except KeyboardInterrupt:
            console.print("\n[info]Use 'exit' to quit[/info]")
            continue
        except Exception as e:
            console.print(f"[error]Error: {str(e)}[/error]")
            continue

if __name__ == "__main__":
    chat() 