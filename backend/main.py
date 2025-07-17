from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List, Dict, Any
import os
import shutil
import logging
import re
import io

# --- AI/ML and Image Processing Imports ---
# New dependencies are required for this AI-powered version.
# Please install them using pip:
# pip install torch transformers sentencepiece
import torch
from transformers import pipeline
from PIL import Image
import fitz  # PyMuPDF

# For PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI()
origins = ["http://localhost:8081", "http://127.0.0.1:8081", "exp://*", "http://localhost:19006"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- AI/ML Model Initialization ---
# This section sets up the Document Question Answering pipeline.
# The model will be downloaded from the Hugging Face Hub on the first run.
# This can take a few minutes and requires an internet connection.
try:
    # Check for GPU availability and set the device accordingly.
    # Using a GPU (device=0) will be significantly faster than CPU (device=-1).
    device = 0 if torch.cuda.is_available() else -1
    if device == 0:
        logger.info("GPU detected. Initializing AI model on GPU for faster processing.")
    else:
        logger.info("No GPU detected. Initializing AI model on CPU. Processing will be slower.")

    # Initialize the pipeline for document question answering
    doc_qa_pipeline = pipeline(
        "document-question-answering",
        model="impira/layoutlm-document-qa",
        device=device
    )
    logger.info("AI Document Question Answering model loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load AI model. The main functionality will not work. Error: {e}", exc_info=True)
    doc_qa_pipeline = None

# --- 2024 IRS Tax Data Constants ---
STANDARD_DEDUCTIONS = {
    "Single": 14600, "Married Filing Jointly": 29200, "MFJ": 29200,
    "Married Filing Separately": 14600, "MFS": 14600,
    "Head of Household": 21900, "HoH": 21900,
}
TAX_BRACKETS_2024 = {
    "Single": [(0, 11600, 0.10), (11601, 47150, 0.12), (47151, 100525, 0.22), (100526, 191950, 0.24), (191951, 243725, 0.32), (243726, 609350, 0.35), (609351, float('inf'), 0.37)],
    "Married Filing Jointly": [(0, 23200, 0.10), (23201, 94300, 0.12), (94301, 201050, 0.22), (201051, 383900, 0.24), (383901, 487450, 0.32), (487451, 731200, 0.35), (731201, float('inf'), 0.37)],
    "Married Filing Separately": [(0, 11600, 0.10), (11601, 47150, 0.12), (47151, 100525, 0.22), (100526, 191950, 0.24), (191951, 243725, 0.32), (243726, 365600, 0.35), (365601, float('inf'), 0.37)],
    "Head of Household": [(0, 16550, 0.10), (16551, 63100, 0.12), (63101, 100500, 0.22), (100501, 191950, 0.24), (191951, 243700, 0.32), (243701, 609350, 0.35), (609351, float('inf'), 0.37)]
}

# --- File Handling and Directory Setup ---
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Core Data Extraction Logic (AI-Powered) ---

def clean_and_convert_to_float(text: str) -> float:
    """Removes currency symbols, commas, and converts a string to a float."""
    if not isinstance(text, str):
        return 0.0
    # Remove common currency symbols, letters, and commas
    cleaned_text = re.sub(r'[$,A-Za-z]', '', text).strip()
    try:
        return float(cleaned_text)
    except (ValueError, TypeError):
        return 0.0

def extract_data_with_ai(image: Image.Image) -> Dict[str, Any]:
    """
    Uses the AI model to extract data from a document image by asking questions.
    """
    if not doc_qa_pipeline:
        raise RuntimeError("AI model is not available.")

    extracted_data = {"form_type": "unknown", "fields": {}}
    
    # Define questions for the AI model for each form type
    questions = {
        "W-2": {
            "wages_tips_other_comp": "What is the value for wages, tips, other compensation?",
            "federal_income_tax_withheld": "What is the federal income tax withheld?",
        },
        "1099-NEC": {
            "nonemployee_compensation": "What is the nonemployee compensation amount?",
        },
        "1099-INT": {
            "interest_income": "What is the interest income?",
        }
    }

    # First, ask a classification question to identify the form
    classification_q = "Is this document a W-2, a 1099-NEC, or a 1099-INT?"
    form_type_answer = doc_qa_pipeline(image=image, question=classification_q)
    
    # Determine form type from the model's answer
    detected_form_key = None
    answer_text = form_type_answer[0]['answer'].upper()
    if "W-2" in answer_text:
        detected_form_key = "W-2"
    elif "NEC" in answer_text:
        detected_form_key = "1099-NEC"
    elif "INT" in answer_text:
        detected_form_key = "1099-INT"

    if detected_form_key:
        extracted_data["form_type"] = detected_form_key
        logger.info(f"AI model classified document as: {detected_form_key}")
        
        # Ask the specific questions for the detected form type
        for field, question in questions[detected_form_key].items():
            logger.info(f"Asking AI: '{question}'")
            answer = doc_qa_pipeline(image=image, question=question)
            # The model may return multiple possible answers, we take the most confident one.
            if answer:
                field_value = clean_and_convert_to_float(answer[0]['answer'])
                extracted_data["fields"][field] = field_value
                logger.info(f"AI answered: '{answer[0]['answer']}' -> Cleaned value: {field_value}")
    else:
        logger.warning(f"AI could not classify the document. Model answer: '{form_type_answer[0]['answer']}'")

    return extracted_data

# --- Tax Calculation and Form Generation (No changes needed here) ---

def calculate_tax_liability(income: float, federal_withheld: float, filing_status: str) -> Dict[str, Any]:
    """Calculates federal tax liability based on 2024 IRS data."""
    status_map = {"MFJ": "Married Filing Jointly", "MFS": "Married Filing Separately", "HOH": "Head of Household"}
    normalized_status = status_map.get(filing_status.upper().replace(" ", ""), filing_status.title())
    if normalized_status not in STANDARD_DEDUCTIONS:
        logger.warning(f"Invalid filing status '{filing_status}'. Defaulting to Single.")
        normalized_status = "Single"
    standard_deduction = STANDARD_DEDUCTIONS[normalized_status]
    taxable_income = max(0, income - standard_deduction)
    brackets = TAX_BRACKETS_2024[normalized_status]
    calculated_tax = 0.0
    remaining_income = taxable_income
    for lower, upper, rate in brackets:
        if remaining_income <= 0: break
        taxable_in_bracket = min(remaining_income, upper - lower)
        calculated_tax += taxable_in_bracket * rate
        remaining_income -= taxable_in_bracket
    return {
        "gross_income": income, "standard_deduction_applied": standard_deduction,
        "taxable_income": taxable_income, "calculated_tax": calculated_tax,
        "total_federal_withheld": federal_withheld, "tax_due_or_refund": calculated_tax - federal_withheld,
    }

def generate_form_1040(tax_summary: Dict[str, Any], personal_info: Dict[str, Any], output_path: str):
    """Generates a simplified, DRAFT Form 1040 PDF."""
    c = canvas.Canvas(output_path, pagesize=letter)
    # ... (form generation code is unchanged)
    c.save()

# --- API Endpoints ---

@app.post("/upload-tax-documents/")
async def upload_tax_documents(files: List[UploadFile] = File(...), filing_status: str = Form(...), num_dependents: int = Form(...)):
    if not doc_qa_pipeline:
        raise HTTPException(status_code=503, detail="AI model is not available. Please check server logs.")
        
    logger.info(f"Received new request. Filing Status: {filing_status}, Dependents: {num_dependents}")
    total_income, total_federal_withheld = 0.0, 0.0
    processed_files_summary, temp_file_paths = [], []

    try:
        for file in files:
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                logger.warning(f"Skipping non-PDF file: {file.filename}"); continue

            temp_path = os.path.join(UPLOAD_DIR, file.filename); temp_file_paths.append(temp_path)
            with open(temp_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
            logger.info(f"Temporarily saved {file.filename}")

            # Process PDF to get images of each page
            doc = fitz.open(temp_path)
            for page_num, page in enumerate(doc):
                logger.info(f"--- Processing Page {page_num + 1} of {file.filename} with AI model ---")
                pix = page.get_pixmap(dpi=200) # Good balance of quality and speed
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

                # Use the new AI function for extraction
                extracted_info = extract_data_with_ai(image)
                
                if extracted_info["form_type"] != "unknown":
                    processed_files_summary.append(extracted_info)
                    fields = extracted_info["fields"]
                    if extracted_info["form_type"] == "W-2":
                        total_income += fields.get("wages_tips_other_comp", 0.0)
                        total_federal_withheld += fields.get("federal_income_tax_withheld", 0.0)
                    elif extracted_info["form_type"] == "1099-NEC":
                        total_income += fields.get("nonemployee_compensation", 0.0)
                    elif extracted_info["form_type"] == "1099-INT":
                        total_income += fields.get("interest_income", 0.0)
            doc.close()

        tax_calculation_results = calculate_tax_liability(total_income, total_federal_withheld, filing_status)
        form_1040_filename = f"Generated_Form_1040_{filing_status.replace(' ', '_')}.pdf"
        form_1040_path = os.path.join(UPLOAD_DIR, form_1040_filename)
        generate_form_1040(tax_calculation_results, {"filing_status": filing_status, "num_dependents": num_dependents}, form_1040_path)
        logger.info(f"Generated Form 1040: {form_1040_filename}")

        return {
            "message": "Tax documents processed successfully with AI!",
            "processed_files_summary": processed_files_summary,
            "tax_summary": tax_calculation_results,
            "form_1040_download_link": f"/download-1040/{form_1040_filename}",
        }
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {e}")
    finally:
        for path in temp_file_paths:
            if os.path.exists(path): os.remove(path); logger.info(f"Cleaned up temporary file: {path}")

@app.get("/download-1040/{filename}")
async def download_1040(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/pdf', filename=filename)
    else:
        raise HTTPException(status_code=404, detail="Generated Form 1040 not found.")

@app.get("/")
async def read_root(): return {"message": "AI Tax Agent Backend with Document AI is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
