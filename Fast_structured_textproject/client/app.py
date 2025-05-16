import requests
import base64
import json

def upload_base64_pdf():
    url = "http://localhost:2000/process-pdf"
    with open('data/gemorder.pdf', 'rb') as f:
        pdf_bytes = f.read()
    encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    payload = {"file_b64": encoded_pdf}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    if response.status_code == 200:
        data = response.json()
        with open("extracted_result.txt", "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=4))
        print("Extracted data saved as 'extracted_result.txt'")
    else:
        print("Error:")

if __name__ == "__main__":
    upload_base64_pdf()
