import fitz  # PyMuPDF
import re
import json
import os
import io

pdf_path = "data/gemorder.pdf"
output_path = "output/tables_output.txt"

def extract_table_section(text):
    start = text.find("\n1\n")
    if start == -1:
        start = text.find("Product Details")
    if start == -1:
        raise Exception("Could not find 'Product Details' table. Please upload a proper PDF.")
    end = text.find("Total Order Value", start)
    if end == -1:
        end = text.find("कुल ऑडQर मूsय", start)
    section = text[start:end] if end != -1 else text[start:]
    return section

def parse_item_description(desc_lines):
    result = {
        "Product Name": "",
        "Brand": "",
        "Brand Type": "",
        "Catalogue Status": "",
        "Selling As": "",
        "Category Name & Quadrant": "",
        "Model": "",
        "HSN Code": ""
    }
    for line in desc_lines:
        m = re.search(r'\|\s*([^:]+)\s*:\s*(.+)', line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
            if key in result:
                result[key] = value
    
    return result

def parse_product_section(section):
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    row_indices = [i for i, line in enumerate(lines) if re.fullmatch(r'\d+', line) and i+1 < len(lines) and '|' in lines[i+1]]
    print(row_indices)
    row_indices.append(len(lines))
    print(row_indices)

    products = {}
    for idx in range(len(row_indices) - 1):
        start = row_indices[idx] + 1
        end = row_indices[idx + 1]
        block = lines[start:end]

        desc_lines = []
        col_values = []
        for i, line in enumerate(block):
            if re.fullmatch(r'\d+', line):
                desc_lines = block[:i]
                col_values = block[i:]
                break
        else:
            desc_lines = block
            col_values = []

        item = parse_item_description(desc_lines)
        
        if len(col_values) >= 6:
            item["Quantity"] = col_values[0]
            item["Unit"] = f"{col_values[1]} {col_values[2]}".strip()
            item["Unit Price"] = col_values[3].replace(",", "")
            item["Tax Bifurcation"] = col_values[4].replace(",", "")
            item["Price"] = col_values[5].replace(",", "")
        else:
            item["Quantity"] = ""
            item["Unit"] = ""
            item["Unit Price"] = ""
            item["Tax Bifurcation"] = ""
            item["Price"] = ""
        item["Inclusive of all Duties and Taxes in INR"] = "Yes"
        
        products[str(idx + 1)] = item
    return {"Product Details": list(products.values())}

def extract_section(text, start_marker, end_marker=None):
    start = text.find(start_marker)
    if start == -1:
        raise Exception(f"Could not find section '{start_marker}'. Please upload a proper PDF.")
    end = text.find(end_marker, start) if end_marker else -1
    return text[start:end] if end != -1 else text[start:]

def clean_section(text):
    lines = text.splitlines()
    clean_lines = []
    seen = set()
    for line in lines:
        line = line.strip()
        if line and line not in seen:
            clean_lines.append(line)
            seen.add(line)
    return clean_lines

def is_hindi_line(line):
    return bool(re.match(r"^[\u0900-\u097F]", line.strip()))

def is_date_or_quantity_line(line):
    line = line.strip()
    return line.isdigit() or re.match(r"\d{2}-[A-Za-z]{3}-\d{4}", line)

def extract_consignee_data(lines):
    rows = []
    designation = "-"
    email = contact = ""
    address_lines = []
    item_blocks = []

    # Step 1: Extract static info and address
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "Designation" in line:
            designation = line.split(":", 1)[1].strip()
        elif "Email ID" in line:
            email = line.split(":", 1)[1].strip()
        elif "Contact" in line:
            contact = line.split(":", 1)[1].strip()
        elif "Address" in line or "पता" in line:
            clean_line = re.sub(r"^(पता\|)?Address\s*:\s*", "", line, flags=re.I).strip()
            address_lines.append(clean_line)
            i += 1
            address_line_count = 1
            while i < len(lines) and address_line_count < 2:
                next_line = lines[i].strip()
                if is_date_or_quantity_line(next_line) or is_hindi_line(next_line) or not re.search(r"[A-Za-z]", next_line):
                    break
                address_lines.append(next_line)
                address_line_count += 1
                i += 1
            break
        i += 1

    # Step 2: Extract item blocks
    while i < len(lines):
        if lines[i].strip() == "":
            i += 1
            continue

        item_desc_lines = []
        while i < len(lines):
            line = lines[i].strip()
            if line.isdigit():
                break
            item_desc_lines.append(line)
            i += 1

        full_desc = ' '.join(item_desc_lines).strip()

        qty = start = end = ""
        if i < len(lines) and lines[i].strip().isdigit():
            qty = lines[i].strip()
            i += 1
        if i < len(lines) and re.match(r"\d{2}-[A-Za-z]{3}-\d{4}", lines[i]):
            start = lines[i].strip()
            i += 1
        if i < len(lines) and re.match(r"\d{2}-[A-Za-z]{3}-\d{4}", lines[i]):
            end = lines[i].strip()
            i += 1

        item_blocks.append((full_desc, qty, start, end))

    # Step 3: Propagate delivery dates
    delivery_start_after = []
    delivery_to_be_completed_by = []
    last_start = ""
    last_end = ""
    for _, _, start, end in item_blocks:
        if start:
            last_start = start
        delivery_start_after.append(last_start)
        if end:
            last_end = end
        delivery_to_be_completed_by.append(last_end)

    # Step 4: Build output
    for idx, block in enumerate(item_blocks):
        row = {
            "designation": designation,
            "email_id": [email],
            "contact": [contact],
            "address": address_lines,
            "item": [block[0]],
            "quantity": [block[1]],
            "delivery_start_after": [delivery_start_after[idx]],
            "delivery_to_be_completed_by": [delivery_to_be_completed_by[idx]]
        }
        rows.append(row)

    return {"consignee_details": rows}

def clean_keys(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            new_key = re.sub(r'[^\w]+', '_', k.lower()).strip('_')
            new_obj[new_key] = clean_keys(v)
        return new_obj
    elif isinstance(obj, list):
        return [clean_keys(item) for item in obj]
    else:
        return obj

def extract_tab(pdf_bytes):
    try:
        b_file = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=b_file, filetype="pdf")

        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"

        product_section = extract_table_section(full_text)
        product_table = parse_product_section(product_section)

        consignee_section = extract_section(full_text, "Consignee Detail", "Product Specification for")
        cleaned_lines = clean_section(consignee_section)
        consignee_data = extract_consignee_data(cleaned_lines)

        output = {}
        output.update(product_table)
        output.update(consignee_data)

        return clean_keys(output)

    except Exception as e:
        print(str(e))
