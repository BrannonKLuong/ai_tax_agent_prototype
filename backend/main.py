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
# Please ensure these are installed: pip install torch transformers sentencepiece
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

# --- CORS Configuration ---
# This list tells your backend which frontend URLs are allowed to make requests.
# We've added a placeholder for your new Netlify site.
origins = [
    "http://localhost:8081", # For local web development
    "http://127.0.0.1:8081",
    "https://your-netlify-app-name.netlify.app", # ** IMPORTANT: REPLACE THIS WITH YOUR ACTUAL NETLIFY URL **
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- AI/ML Model Initialization ---
try:
    device = 0 if torch.cuda.is_available() else -1
    log_msg = "GPU detected. Initializing AI model on GPU." if device == 0 else "No GPU detected. Initializing AI model on CPU."
    logger.info(log_msg)
    doc_qa_pipeline = pipeline("document-question-answering", model="impira/layoutlm-document-qa", device=device)
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
    """
    Robustly cleans and converts a string to a float. It finds all potential numbers
    and returns the most likely one (usually the largest if multiple are present).
    """
    if not isinstance(text, str) or not any(char.isdigit() for char in text):
        return 0.0
    
    potential_numbers = re.findall(r'[\d,]+\.?\d*', text)
    if not potential_numbers:
        return 0.0
    
    valid_numbers = []
    for num_str in potential_numbers:
        cleaned_str = num_str.replace(',', '').replace('$', '').strip()
        if cleaned_str:
            try:
                valid_numbers.append(float(cleaned_str))
            except ValueError:
                continue
            
    return max(valid_numbers) if valid_numbers else 0.0

def is_likely_tax_form_page(page_text: str) -> bool:
    """
    A heuristic to determine if a page is likely a real tax form and not just instructions.
    Real forms usually contain multiple of these keywords in a structured way.
    """
    form_indicators = [
        r"OMB No\.",
        r"Employer identification number",
        r"PAYER'S.*TIN",
        r"RECIPIENT'S.*TIN",
        r"Copy [A-Z0-9]",
        r"Form \d{4}-?[A-Z]{2,3}"
    ]
    
    match_count = sum(1 for pattern in form_indicators if re.search(pattern, page_text, re.IGNORECASE))
    return match_count >= 2

def extract_data_with_ai(image: Image.Image, page_text: str) -> Dict[str, Any]:
    """
    Uses a more precise pre-filtering check and more specific questions to guide the AI model.
    """
    if not doc_qa_pipeline:
        raise RuntimeError("AI model is not available.")

    extracted_data = {"form_type": "unknown", "fields": {}}
    
    if not is_likely_tax_form_page(page_text):
        logger.info("Page does not appear to be a standard tax form based on structural keywords. Skipping AI analysis.")
        return extracted_data

    logger.info("Page appears to be a real tax form. Running AI analysis.")
    
    form_type_keywords = {
        "W-2": "Wages, tips, other compensation",
        "1099-NEC": "Nonemployee compensation",
        "1099-INT": "Interest Income"
    }
    
    detected_form_key = "unknown"
    for form, keyword in form_type_keywords.items():
        if re.search(keyword, page_text, re.IGNORECASE):
            detected_form_key = form
            break
            
    if detected_form_key == "unknown":
        logger.warning("Could not determine form type for this page, despite it looking like a form.")
        return extracted_data

    extracted_data["form_type"] = detected_form_key
    logger.info(f"Form type classified as: {detected_form_key}")

    questions = {
        "W-2": {
            "wages_tips_other_comp": "What is the amount in box 1 for 'Wages, tips, other compensation'?",
            "federal_income_tax_withheld": "What is the amount in box 2 for 'Federal income tax withheld'?",
        },
        "1099-NEC": {
            "nonemployee_compensation": "What is the amount in box 1 for 'Nonemployee compensation'?",
        },
        "1099-INT": {
            "interest_income": "What is the amount in box 1 for 'Interest Income'?",
        }
    }

    CONFIDENCE_THRESHOLD = 0.1

    for field, question in questions[detected_form_key].items():
        logger.info(f"Asking AI: '{question}'")
        answer = doc_qa_pipeline(image=image, question=question)
        if answer:
            best_answer = sorted(answer, key=lambda x: x['score'], reverse=True)[0]
            score = best_answer['score']
            
            if score >= CONFIDENCE_THRESHOLD:
                field_value = clean_and_convert_to_float(best_answer['answer'])
                extracted_data["fields"][field] = field_value
                logger.info(f"AI answered: '{best_answer['answer']}' (Score: {score:.2f}) -> Cleaned value: {field_value}")
            else:
                logger.warning(f"AI answer '{best_answer['answer']}' rejected due to low confidence score ({score:.2f}).")
            
    return extracted_data


# --- Tax Calculation and Form Generation ---

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
    """Generates a simplified, DRAFT Form 1040 PDF with populated fields."""
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, height - 72, "DRAFT - Form 1040 (2024)")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 90, "This is a computer-generated draft for demonstration purposes only.")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, height - 120, "Filing Information")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 135, f"Filing Status: {personal_info.get('filing_status', 'N/A')}")
    c.drawString(72, height - 150, f"Dependents: {personal_info.get('num_dependents', 'N/A')}")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, height - 200, "Income & Deductions")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 215, f"Gross Income (from all forms):")
    c.drawString(450, height - 215, f"${tax_summary.get('gross_income', 0.0):,.2f}")
    
    c.drawString(72, height - 230, f"Standard Deduction ({personal_info.get('filing_status', 'N/A')}):")
    c.drawString(450, height - 230, f"${tax_summary.get('standard_deduction_applied', 0.0):,.2f}")

    c.line(72, height - 240, 522, height - 240)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, height - 255, f"Taxable Income:")
    c.drawString(450, height - 255, f"${tax_summary.get('taxable_income', 0.0):,.2f}")


    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, height - 300, "Tax, Payments, and Refund")
    c.setFont("Helvetica", 10)
    c.drawString(72, height - 315, f"Calculated Tax:")
    c.drawString(450, height - 315, f"${tax_summary.get('calculated_tax', 0.0):,.2f}")
    
    c.drawString(72, height - 330, f"Total Federal Tax Withheld:")
    c.drawString(450, height - 330, f"${tax_summary.get('total_federal_withheld', 0.0):,.2f}")

    c.line(72, height - 340, 522, height - 340)

    c.setFont("Helvetica-Bold", 12)
    final_amount = tax_summary.get('tax_due_or_refund', 0.0)
    if final_amount < 0:
        c.setFillColorRGB(0, 0.5, 0)
        c.drawString(72, height - 360, f"Your Estimated REFUND:")
        c.drawString(450, height - 360, f"${abs(final_amount):,.2f}")
    else:
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(72, height - 360, f"Amount YOU OWE:")
        c.drawString(450, height - 360, f"${final_amount:,.2f}")
    
    c.showPage()
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

            doc = fitz.open(temp_path)
            for page_num, page in enumerate(doc):
                logger.info(f"--- Analyzing Page {page_num + 1} of {file.filename} ---")
                
                pix = page.get_pixmap(dpi=200)
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                page_text = page.get_text("text")

                extracted_info = extract_data_with_ai(image, page_text)
                
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
