from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import base64

import os

from src.main1 import extract_main
from src.newtab import extract_tab




app = FastAPI()



class PDFBase64Request(BaseModel):
    file_b64: str

@app.post("/process-pdf")
async def process_pdf(request: PDFBase64Request):
    try:
        
        # geeting pff bytes from base 64 decode
        pdf_bytes = base64.b64decode(request.file_b64)
        # testing to store in temparaty location
        
        
        result_main = extract_main(pdf_bytes)
        result_newtab = extract_tab(pdf_bytes)
        

        result={
            "section_result":result_main,
            "all_tables_result":result_newtab
        }
        
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500)
