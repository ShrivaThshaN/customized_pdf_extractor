import PyPDF2
import re
import json
import os
import io


def is_mainly_english(text):
    if not text.strip():
        return False
    english_chars = 0
    non_english_chars = 0
    for char in text:
        if char.isspace() or char.isdigit() or char in ".,;:!?-_()[]{}'\"/\\@#$%^&*+=<>|~`":
            continue
        if 'A' <= char <= 'Z' or 'a' <= char <= 'z':
            english_chars += 1
        else:
            if char not in '₹€£¥$©®™°':
                non_english_chars += 1
    return english_chars / (english_chars + non_english_chars + 0.001) >= 0.7

def extract_text_from_pdf_bytes(pdf_bytes):
    try:
        b_file=io.BytesIO(pdf_bytes)
        reader = PyPDF2.PdfReader(b_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                english_lines = [line for line in page_text.split('\n') if is_mainly_english(line)]
                text += '\n'.join(english_lines) + '\n'
        return text
    except Exception as e:
        raise Exception(f"Failed to read PDF: {e}")



def identify_sections(text):
    # Special handling to extract contract section from the top
    contract_match = re.search(r'Contract No:.*?(?:\n|$).*?Generated Date.*?(?:\n|$).*?Bid/RA/PBP No.*?(?:\n|$)', text, re.DOTALL | re.IGNORECASE)
    
    header_positions = []

    if contract_match:
        contract_start = contract_match.start()
        contract_end = contract_match.end()
        # contract_section = text[contract_start:contract_end].strip()
        header_positions.append((contract_start, "contract"))
    
    # Normal section pattern (like Organisation Details etc.)
    section_pattern = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Details?)\s*', re.MULTILINE)
    for match in section_pattern.finditer(text):
        pos = match.start()
        name = match.group(1).strip().lower().replace(' ', '_')
        if name != 'contract':  # skip duplicate
            header_positions.append((pos, name))
    
    # Sort positions
    header_positions.sort()

    # Build sections based on boundaries
    sections = {}
    for i in range(len(header_positions)):
        start = header_positions[i][0]
        name = header_positions[i][1]
        end = header_positions[i + 1][0] if i + 1 < len(header_positions) else None
        section_text = text[start:end].strip() if end else text[start:].strip()
        sections[name] = section_text
        

    return sections


def clean_key_value_pair(key, value):
    
    key = key.strip().lower()
    # Strip leading/trailing whitespace
    key = key.strip()
    

    # Replace all non-alphanumeric characters with underscore
    key = re.sub(r'[^a-zA-Z0-9]', '_', key)

    
    

    # Replace multiple underscores with a single one
    key = re.sub(r'_+', '_', key)

    # Strip any leading/trailing underscores
    key = key.strip('_')

    # Clean value
    value = re.sub(r'\s*\|.*$', '', value).strip()
    
    return key, value


def extract_key_value_pairs(section_text):
    pairs = []
    lines = section_text.split('\n')
    current_key = None
    current_value = None
    

    for line in lines:
        
        line_text = line.strip()
        if not line_text or not is_mainly_english(line_text):
            continue

        
        # Check for separator
        if ':' in line_text or '|' in line_text:
            sep = ':' if ':' in line_text else '|'
            parts = line_text.split(sep, 1)
            if len(parts) == 2 and parts[0].strip() and len(parts[0]) < 100:
                if current_key and current_value:
                    cleaned_key, cleaned_value = clean_key_value_pair(current_key, current_value)
                    pairs.append({cleaned_key: cleaned_value})
                current_key = parts[0].strip()
                current_value = parts[1].strip()
        else:
            # Fallback: Try to match format like 'Contact No. 044-28251472'
            match = re.match(r'^([A-Za-z0-9 .]+?)\s{2,}(.+)$', line_text)
            if match:
                if current_key and current_value:
                    cleaned_key, cleaned_value = clean_key_value_pair(current_key, current_value)
                    pairs.append({cleaned_key: cleaned_value})
                current_key = match.group(1).strip()
                current_value = match.group(2).strip()
            elif current_key:
                # Append multiline value if it's not a new section
                if not re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+Details?', line_text):
                    current_value += " " + line_text

    if current_key and current_value:
        cleaned_key, cleaned_value = clean_key_value_pair(current_key, current_value)
        pairs.append({cleaned_key: cleaned_value})

    return pairs


def extract_main(pdf_bytes):
    
    text = extract_text_from_pdf_bytes(pdf_bytes)

   
    sections = identify_sections(text)
    required_sections = {
        "contract",
        "organisation_details",
        "buyer_details",
        "financial_approval_detail",
        "paying_authority_details",
        "seller_details"
    }
    # finding whether sections are avaialble in pdf. so that it is the correct gem pdf
    found_sections = set(sections.keys())
    missing = required_sections - found_sections
    if missing:
        raise Exception(f"Missing required sections: {', '.join(missing)}")
    # 
    structured_data = {}
    for section_name, section_text in sections.items():
        if section_name in ["product_details", "consignee_detail"]:
            continue  # skip unwanted sections
        pairs = extract_key_value_pairs(section_text)
        if pairs:
            structured_data[section_name] = pairs

 

    return structured_data
