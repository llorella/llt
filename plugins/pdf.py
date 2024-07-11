from typing import List, Dict
import pdfplumber
from plugins import plugin

def extract_text_by_headings(pdf_path):
    """Extract text from a PDF file and group it by headings."""
    text_sections = {}
    current_heading = "Introduction"
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = text.split("\n")
                for line in lines: print(line)
               
    return text_sections

from utils import path_input
import os
@plugin
def pdf_load(messages: List[Dict], args: Dict) -> List[Dict]:
    pdf_path = os.path.expanduser(path_input(None, "~/papers"))
    if not pdf_path: print("No PDF file specified.")
    elif os.path.splitext(pdf_path)[-1] != '.pdf': print("Invalid PDF file. Please provide a PDF file.")
    else:
        text_sections = extract_text_by_headings(pdf_path)
    return messages