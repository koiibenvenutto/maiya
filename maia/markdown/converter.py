"""
Convert Notion blocks to markdown format.
"""
from typing import Dict, Any, List
import re

def block_to_markdown(block: Dict[str, Any], level: int = 0) -> str:
    """
    Convert a Notion block to markdown format.
    
    Args:
        block: Notion block object to convert
        level: Indentation level for nested blocks
        
    Returns:
        Markdown representation of the block
    """
    block_type = block["type"]
    content = block[block_type]
    markdown = ""
    indent = "    " * level

    try:
        # Extract text content from any block type
        if block_type == "code":
            # For code blocks, get text from the code property's rich_text
            text = "".join(
                [
                    span.get("text", {}).get("content", "")
                    for span in content.get("rich_text", [])
                ]
            )
            
            # Get code block properties
            language = content.get("language", "")
            
            # Format the code block with language specification
            markdown = f"{indent}```{language}\n"
            
            # Add the code content with proper indentation
            code_lines = text.split("\n")
            for line in code_lines:
                markdown += f"{indent}{line}\n"
            
            # Close the code block
            markdown += f"{indent}```\n"  # Add line break after code block
            
            # Add caption if present (safely handle empty caption array)
            caption_text = ""
            if content.get("caption"):
                caption_text = "".join(
                    [
                        span.get("text", {}).get("content", "")
                        for span in content["caption"]
                    ]
                )
            if caption_text:
                markdown += f"{indent}*{caption_text}*\n"  # Add line break after caption
        else:
            # For other blocks, get text from the block's rich_text with formatting
            text = format_rich_text(content.get("rich_text", []))
            
            # Handle different block types
            if block_type == "paragraph":
                if text:
                    markdown = f"{indent}{text}\n\n"
                else:
                    markdown = f"{indent}\n\n"  # Empty paragraph gets a blank line
            
            elif block_type == "heading_1":
                markdown = f"{indent}# {text}\n\n"
            
            elif block_type == "heading_2":
                markdown = f"{indent}## {text}\n\n"
            
            elif block_type == "heading_3":
                markdown = f"{indent}### {text}\n\n"
                
            elif block_type == "bulleted_list_item":
                markdown = f"{indent}- {text}\n"
                
            elif block_type == "numbered_list_item":
                markdown = f"{indent}1. {text}\n"
                
            elif block_type == "to_do":
                checked = content.get("checked", False)
                checkbox = "x" if checked else " "
                markdown = f"{indent}- [{checkbox}] {text}\n"
                
            elif block_type == "toggle":
                markdown = f"{indent}> **{text}**\n"
                
            elif block_type == "quote":
                markdown = f"{indent}> {text}\n\n"
                
            elif block_type == "divider":
                markdown = f"{indent}---\n\n"
                
            elif block_type == "callout":
                emoji = content.get("icon", {}).get("emoji", "")
                markdown = f"{indent}> {emoji} **{text}**\n\n"
                
            elif block_type == "image":
                caption = format_rich_text(content.get("caption", []))
                # Try to get the URL from various sources
                url = ""
                image_type = content.get("type", "")
                
                if image_type == "external":
                    url = content.get("external", {}).get("url", "")
                elif image_type == "file":
                    url = content.get("file", {}).get("url", "")
                
                markdown = f"{indent}![{caption}]({url})\n\n"
                if caption:
                    markdown += f"{indent}*{caption}*\n\n"
            
            elif block_type == "bookmark":
                url = content.get("url", "")
                caption = format_rich_text(content.get("caption", []))
                markdown = f"{indent}[{url}]({url})\n"
                if caption:
                    markdown += f"{indent}*{caption}*\n\n"
            
            elif block_type == "embed":
                url = content.get("url", "")
                markdown = f"{indent}<{url}>\n\n"
                
            elif block_type == "table":
                # Tables are complex, and their content is in children
                # We'll handle table blocks later
                markdown = f"{indent}[Table content not supported yet]\n\n"
            
            elif block_type == "column_list" or block_type == "column":
                # These blocks are just containers, so we'll skip them
                # and rely on processing their children
                pass
            
            else:
                # Default for unhandled block types
                markdown = f"{indent}*[{block_type} block]*: {text}\n\n"
    except Exception as e:
        # If there's an error processing this block, at least give a hint
        markdown = f"{indent}*[Error processing {block_type} block: {str(e)}]*\n\n"
    
    # Process children blocks if they exist
    if block.get("children"):
        child_markdown = ""
        for child in block["children"]:
            child_markdown += block_to_markdown(child, level + 1)
        
        # For some block types, we want to indent the children differently
        if block_type in ["bulleted_list_item", "numbered_list_item"]:
            # Replace the existing double newline with a single one before adding children
            markdown = markdown.rstrip() + "\n" + child_markdown
        else:
            markdown += child_markdown
            
    return markdown

def format_rich_text(rich_text_array):
    """
    Format rich text array from Notion into markdown.
    
    Args:
        rich_text_array: Array of rich text objects from Notion
        
    Returns:
        Formatted markdown text
    """
    if not rich_text_array:
        return ""
    
    result = ""
    for text_obj in rich_text_array:
        text = text_obj.get("text", {}).get("content", "")
        annotations = text_obj.get("annotations", {})
        
        # Apply text annotations (bold, italic, etc.)
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("underline"):
            # Markdown doesn't directly support underline, using emphasis instead
            text = f"_{text}_"
        
        # Handle links
        if text_obj.get("href"):
            text = f"[{text}]({text_obj['href']})"
        
        result += text
    
    return result

def page_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert a list of Notion blocks to a complete markdown document.
    
    Args:
        blocks: List of Notion blocks
        
    Returns:
        Complete markdown document as a string
    """
    markdown = ""
    for block in blocks:
        markdown += block_to_markdown(block)
    
    return markdown 