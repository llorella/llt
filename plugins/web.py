#!/usr/bin/python3
import sys
from collections import namedtuple
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from typing import List, Dict, Optional, Union, Tuple, Callable
from urllib.parse import urlparse
import json

from utils.helpers import get_valid_index, Colors
from plugins import plugin
from logger import llt_logger

# Basic data structures
ContentBlock = namedtuple('ContentBlock', ['type', 'content', 'attributes'])

def fetch_url(url: str) -> Optional[str]:
    """Fetch content from URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        llt_logger.log_error(f"Error fetching URL {url}", {"error": str(e)})
        return None

def parse_html(html_content: str) -> Optional[BeautifulSoup]:
    """Parse HTML content into BeautifulSoup object."""
    try:
        return BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        llt_logger.log_error("Error parsing HTML", {"error": str(e)})
        return None

def extract_metadata(soup: BeautifulSoup, url: str) -> Dict:
    """Extract metadata from HTML."""
    return {
        'title': soup.title.string if soup.title else None,
        'description': soup.find('meta', {'name': 'description'})['content'] 
                      if soup.find('meta', {'name': 'description'}) else None,
        'url': url
    }

def determine_block_type(element: Tag) -> str:
    """Determine content block type based on HTML element."""
    if element.name == 'pre' or element.find('code'):
        return 'code'
    elif element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        return 'header'
    elif element.find('a'):
        return 'link'
    return 'text'

def extract_code_content(element: Tag) -> str:
    """Extract code content from a pre/code element."""
    code_element = element.find('code') or element
    # Preserve newlines and indentation in code blocks
    return code_element.get_text(strip=False).strip()

def extract_text_content(element: Tag) -> str:
    """Extract and clean text content from an element."""
    content_parts = []
    for child in element.children:
        if isinstance(child, NavigableString):
            content_parts.append(str(child).strip())
        elif child.name in ['a', 'strong', 'em', 'code']:
            content_parts.append(child.get_text().strip())
        elif child.name in ['br', 'p']:
            content_parts.append('\n')
    # Join with space but preserve intentional newlines
    return ' '.join(part for part in content_parts if part).replace('\n ', '\n')

def format_block(block: ContentBlock) -> str:
    """Format a single content block."""
    if block.type == 'code':
        # Properly format code blocks with language hint if available
        lang = block.attributes.get('class', [''])[0].replace('language-', '') if block.attributes.get('class') else ''
        return f"```{lang}\n{block.content}\n```"
    elif block.type == 'header':
        return f"\n## {block.content}"
    elif block.type == 'link':
        return block.content
    return block.content

def format_content(blocks: List[ContentBlock]) -> str:
    """Format all content blocks into readable text."""
    formatted_blocks = []
    for block in blocks:
        formatted = format_block(block)
        # Ensure proper spacing between blocks
        if formatted.strip():
            formatted_blocks.append(formatted)
    
    # Join blocks with double newlines for readability
    return '\n\n'.join(formatted_blocks)

def extract_block_content(element: Tag) -> str:
    """Extract content based on element type."""
    if element.name == 'pre' or element.find('code'):
        return extract_code_content(element)
    return extract_text_content(element)

def find_content_blocks(soup: BeautifulSoup, tags: List[str], attributes: Dict = None) -> List[ContentBlock]:
    """Find and extract content blocks based on specified tags."""
    blocks = []
    attributes = attributes or {}
    
    for tag in tags:
        elements = soup.find_all(tag, attributes)
        for element in elements:
            block_type = determine_block_type(element)
            content = extract_block_content(element)
            if content:
                blocks.append(ContentBlock(block_type, content, dict(element.attrs)))
    
    return blocks



def valid_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def process_url(url: str, tags: List[str], include_metadata: bool = False) -> Optional[Tuple[str, Dict]]:
    """Process a URL and return formatted content and metadata."""
    if not valid_url(url):
        llt_logger.log_error(f"Invalid URL provided: {url}")
        return None
    
    html_content = fetch_url(url)
    if not html_content:
        return None
    
    soup = parse_html(html_content)
    if not soup:
        return None
    
    metadata = extract_metadata(soup, url)
    blocks = find_content_blocks(soup, tags)
    formatted_content = format_content(blocks)
    
    if include_metadata:
        metadata_str = json.dumps(metadata, indent=2)
        formatted_content = f"Metadata:\n{metadata_str}\n\nContent:\n{formatted_content}"
    
    return formatted_content, metadata

DEFAULT_TAGS = {
    'content': [
        'p',          # paragraphs - main content
        'h1', 'h2', 'h3', 'h4',  # headers - structure
        'pre',        # code blocks
        'ul', 'ol',   # lists
        'table',      # tables
        'blockquote', # quotes/callouts
        'div.tip'     # special content blocks (like tips)
    ],
    'metadata': [
        'title',      # page title
        'meta[name="description"]',  # page description
        'meta[name="keywords"]'      # page keywords
    ],
    'ignore': [
        'nav',        # navigation elements
        'footer',     # footer elements
        'script',     # scripts
        'style',      # styles
        'noscript'    # noscript content
    ]
}

# Tag groups for specific use cases
TAG_GROUPS = {
    'code': ['pre', 'code'],
    'text': ['p', 'blockquote'],
    'structure': ['h1', 'h2', 'h3', 'h4'],
    'lists': ['ul', 'ol', 'li'],
    'tables': ['table', 'tr', 'td', 'th'],
}

def get_tags_for_type(content_type: str) -> List[str]:
    """Get appropriate tags based on content type."""
    return TAG_GROUPS.get(content_type, DEFAULT_TAGS['content'])

@plugin    
def url_fetch(messages: List[Dict[str, any]], args: Dict, index: int = -1) -> List[Dict[str, any]]:
    """Plugin function to fetch and process URL content."""
    # Get URL from arguments or message content
    if not args.url_fetch:
        index = get_valid_index(messages, "fetch url from", index)

    url = messages[index]["content"]
    # Handle tags based on args
    if hasattr(args, 'tags') and args.tags:
        if isinstance(args.tags, str):
            # Handle tag group specification
            tags = get_tags_for_type(args.tags)
        else:
            # Use specified tags
            tags = args.tags
    else:
        # Use default content tags
        tags = DEFAULT_TAGS['content']
    
    # Process URL
    result = process_url(
        url=url,
        tags=tags,
        include_metadata=getattr(args, 'include_metadata', False)
    )
    
    if result:
        formatted_content, metadata = result
        messages.append({
            'role': args.role,
            'content': formatted_content
        })
        
        llt_logger.log_info("URL content fetched and processed", {
            "url": url,
            "tags_used": tags,
            "content_length": len(formatted_content),
            **metadata
        })
    
    args.url_fetch = False
    return messages

def main() -> int:
    """Command line interface for URL processing."""
    if len(sys.argv) >= 2:
        url = sys.argv[1]
        content_type = sys.argv[2] if len(sys.argv) == 3 else 'content'
        
        from argparse import Namespace
        args = Namespace(
            role='user', 
            tags=get_tags_for_type(content_type),
            url=url, 
            include_metadata=True
        )
        
        result = url_fetch([{'role': 'user', 'content': url}], args, 0)
        Colors.print_colored(json.dumps(result, indent=2), Colors.GREEN)
        return 0
    
    Colors.print_colored("Usage: script.py <url> [content_type]", Colors.RED)
    return 1

if __name__ == "__main__":
    sys.exit(main())
    
    #!/usr/bin/python3
