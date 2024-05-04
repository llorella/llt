#bin/python
from bs4 import BeautifulSoup
import sys
from collections import namedtuple
import requests
import json
import re
from typing import List, Dict

from utils import get_valid_index
from message import Message

CodeBlock = namedtuple('CodeBlock', ['description', 'code', 'language'])

def fetch_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return None
    
def find_tags(html_content, tag: str = 'p', attributes: dict = {}):
    soup = BeautifulSoup(html_content, 'html.parser')
    paragraphs = soup.find_all(tag, attributes)
    return paragraphs

def find_code_block_description(code_block):
    paragraphs = []
    parent, i = code_block, 0
    while i < 5:
        for sibling in parent.find_previous_siblings(limit=5):
            if sibling.name == "p": paragraphs.append(sibling.get_text())
            elif paragraphs: break  # stop filling paragraphs once we reach a non-paragraph element
        parent, i = parent.parent, i + 1
    description = "\n".join(reversed(paragraphs))
    return description
    
def get_code_blocks_from_tags(tags) -> list[CodeBlock]:
    blocks_list = []
    for tag in tags:
        description = find_code_block_description(tag)
        code = tag.find('code').get_text(strip=True) if tag.find('code') else tag.get_text(strip=True)
        language = tag.find('code')['data-lang'] if tag.find('code') and 'data-lang' in tag.find('code').attrs else "Unknown"
        blocks_list.append(CodeBlock(description=description, code=code, language=language))
    return blocks_list

def valid_url(url):
    pattern = re.compile(
        r'^(https?://)[\w\-]+(\.[\w\-]+)+([\w\-\.,@?^=%&:/~\+#]*[\w\-\@?^=%&/~\+#])?$'
    )
    if pattern.match(url):
        return True
    else:
        return False
    
def process_web_request(messages: List[Message], args: Dict, index: int = -1) -> list[dict[str, any]]:
    message_index = get_valid_index(messages, "fetch url from", index)
    messages[message_index]['content'] = get_code_blocks_from_tags(find_tags(html_content=fetch_html(messages[message_index]['content']), tag='pre') 
                                                                   if valid_url(messages[message_index]['content']) 
                                                                   else "Invalid URL. Please provide a valid URL.")
    return messages

def main():
    if len(sys.argv) == 2:
        url = sys.argv[1]
        if not valid_url(url):
            print("Invalid URL. Please provide a valid URL.")
            return 
        print(f"Fetching URL: {url}")
        print(json.dumps(process_web_request([{'role': 'user', 'content': url}], None, 0), indent=2))
    else:
        print("Usage: script.py <url>")
    return 0

if __name__ == "__main__":
    main()