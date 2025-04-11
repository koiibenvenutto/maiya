#!/usr/bin/env python
"""
Compatibility wrapper for the old chat.py script.
This script maintains backward compatibility while using the new modular structure.
"""
import os
import sys

# Add the current directory to the path to ensure maia package is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Entry point for the compatibility wrapper."""
    try:
        from maia.chat.interface import chat
        
        # Run the chat interface
        chat()
    except ImportError as e:
        print(f"Error loading chat interface: {str(e)}")
        print("Make sure you have installed the package correctly.")
        print("Try running: pip install -e .")

if __name__ == "__main__":
    main() 