from anthropic import Anthropic
from dotenv import load_dotenv
import os
import glob
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
                'filename': os.path.basename(file_path)
            })
    
    return pages

def create_system_prompt(pages):
    """Create a system prompt that includes the context from markdown files."""
    # Read project instructions
    with open('project-instructions.md', 'r', encoding='utf-8') as f:
        instructions = f.read()
    
    # Start with project instructions
    context = f"{instructions}\n\n"
    context += "Here are some journal entries that provide additional context for our conversation:\n\n"
    
    for page in pages:
        context += f"=== {page['filename']} ===\n{page['content']}\n\n"
    
    context += "\nPlease use this context to inform your responses. You can reference specific entries when relevant."
    return context

def chat():
    """Main chat loop."""
    # Read markdown files for context
    print("Loading journal entries...")
    pages = read_markdown_files()
    print(f"Loaded {len(pages)} journal entries")
    
    # Create system prompt with context
    system_prompt = create_system_prompt(pages)
    
    # Initialize conversation history
    messages = []
    
    print("\nWelcome to Claude Chat! Type 'exit' to quit, 'clear' to start a new conversation, 'sync' to refresh from Notion.")
    print("=" * 80)
    
    while True:
        try:
            # Get user input
            user_input = session.prompt(
                "\nYou: ",
                style=style,
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(['exit', 'clear', 'help', 'sync'])
            )
            
            # Handle special commands
            if user_input.lower() == 'exit':
                print("\nGoodbye!")
                break
            elif user_input.lower() == 'clear':
                messages = []
                print("\nConversation cleared!")
                continue
            elif user_input.lower() == 'help':
                print("\nAvailable commands:")
                print("- exit: Exit the chat")
                print("- clear: Clear conversation history")
                print("- sync: Refresh content from Notion")
                print("- help: Show this help message")
                continue
            elif user_input.lower() == 'sync':
                print("\nSyncing with Notion...")
                try:
                    # Run the Notion sync script
                    import subprocess
                    result = subprocess.run(['python', 'get-notion-database.py'], 
                                         capture_output=True, 
                                         text=True)
                    
                    if result.returncode == 0:
                        # Reload markdown files
                        pages = read_markdown_files()
                        system_prompt = create_system_prompt(pages)
                        print(f"Successfully synced {len(pages)} journal entries")
                        print("=" * 80)
                    else:
                        print("Error syncing with Notion:")
                        print(result.stderr)
                except Exception as e:
                    print(f"Error during sync: {str(e)}")
                continue
            
            # Add user message to history
            messages.append({"role": "user", "content": user_input})
            
            # Get Claude's response
            response = client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=4000,
                messages=messages,
                system=system_prompt
            )
            
            # Add Claude's response to history
            messages.append({"role": "assistant", "content": response.content[0].text})
            
            # Print Claude's response
            print("\nClaude:", response.content[0].text)
            
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {str(e)}")

if __name__ == "__main__":
    chat() 