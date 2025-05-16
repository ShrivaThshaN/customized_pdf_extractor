# TextProject Software Package

## Structure
- `app.py` - Master launcher script
- `requirements.txt` - Required Python packages
- `src/` - Source scripts
- `data/` - Input PDFs
- `output/` - Extracted text or JSON results

## How to Run
```bash
python app.py
```
Make sure to put your PDF files inside the `data/` directory before running.

uvicorn server.api_server:app --reload --port=2000
