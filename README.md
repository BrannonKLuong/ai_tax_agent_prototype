# AI Tax Return Agent Prototype

This project is a functional, end-to-end prototype of an AI agent that automates personal tax return preparation. It allows users to upload standard U.S. tax documents (W-2, 1099-NEC, 1099-INT), extracts relevant financial data using a Document AI model, calculates the user's estimated tax liability, and generates a simplified Form 1040 PDF.

## Features

* **Cross-Platform Frontend**: Built with React Native, allowing it to run on web browsers, iOS, and Android.
* **Multi-Document Upload**: Users can select and upload multiple PDF tax forms at once.
* **Intelligent Document Processing**: The Python backend uses a state-of-the-art AI model (`impira/layoutlm-document-qa`) to:
    * Automatically classify each uploaded document (W-2, 1099-NEC, etc.).
    * Extract key financial data by asking natural language questions (e.g., "What is the amount in box 1 for Wages?").
    * Intelligently filter out irrelevant instructional pages from documents.
* **Automatic Tax Calculation**: Aggregates all extracted income and withholdings and calculates the estimated tax due or refund based on 2024 IRS tax brackets and standard deductions.
* **PDF Form Generation**: Dynamically generates a simplified, DRAFT Form 1040 PDF populated with the calculated results.
* **Clean, Responsive UI**: The user interface is designed to be clear and easy to use, providing detailed feedback on the extracted data and final calculations.

## Tech Stack

| Area      | Technology                                                              | Description                                                                 |
| :-------- | :---------------------------------------------------------------------- | :-------------------------------------------------------------------------- |
| **Frontend** | **React Native** & **Expo** | For building a cross-platform user interface.                               |
| **Backend** | **Python** & **FastAPI** | For creating a fast, modern, and scalable API server.                       |
| **AI / ML** | **PyTorch** & **Hugging Face Transformers** | To run the `impira/layoutlm-document-qa` model for document understanding.  |
| **PDF Tools** | **PyMuPDF (fitz)**, **Pillow**, **ReportLab** | For reading PDF content, processing images for the AI, and generating the final Form 1040. |

## Project Setup and Installation

### Prerequisites

* Node.js and npm/yarn for the frontend.
* Python 3.8+ and `pip` for the backend.
* **Tesseract OCR Engine**: The AI model relies on OCR. Install it on your system:
    * **Windows**: Download from the [official Tesseract repository](https://github.com/UB-Mannheim/tesseract/wiki).
    * **macOS**: `brew install tesseract`
    * **Linux (Ubuntu)**: `sudo apt-get install tesseract-ocr`

### Backend Setup

1.  **Navigate to the `backend` directory:**
    ```bash
    cd /path/to/your/project/backend
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install "fastapi[all]" torch transformers sentencepiece Pillow PyMuPDF reportlab python-multipart
    ```
    *Note: For significant performance improvement on NVIDIA GPUs, install the CUDA-enabled version of PyTorch.*

4.  **Configure Tesseract Path (if needed):**
    * Open `main.py` and ensure the `pytesseract.pytesseract.tesseract_cmd` path is correct for your system.

### Frontend Setup

1.  **Navigate to the `frontend/TaxAgentApp` directory:**
    ```bash
    cd /path/to/your/project/frontend/TaxAgentApp
    ```
2.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

## How to Run the Application

1.  **Start the Backend Server:**
    * In your terminal, from the `backend` directory, run:
        ```bash
        uvicorn main:app --reload
        ```
    * The first time you run this, it will download the AI model from Hugging Face (approx. 1-2 GB). This is a one-time process.
    * The backend will be running at `http://localhost:8000`.

2.  **Start the Frontend Application:**
    * In a **new** terminal, from the `frontend/TaxAgentApp` directory, run:
        ```bash
        npm start
        ```
    * Expo will start the development server. You can then choose to open the app in a web browser, on an iOS simulator, or on an Android emulator.

3.  **Use the App:**
    * The app will open in your browser at `http://localhost:8081` (or as specified by Expo).
    * Enter your filing status and number of dependents.
    * Click "Select Documents" to upload your sample PDF tax forms.
    * Click "Calculate Tax Return" to send the files to the backend for AI processing.
    * View the results and download your generated Form 1040.

## Future Improvements

* **Support for More Forms**: Extend the AI logic to handle other common forms like 1098 (Mortgage Interest), Schedule C (Business Income), etc.
* **Itemized Deductions**: Implement logic to allow users to choose between the standard deduction and itemized deductions.
* **Enhanced Security**: For a production application, implement robust security measures, including data encryption at rest and in transit, and secure handling of Personally Identifiable Information (PII).
* **State Tax Returns**: Add modules to calculate state tax liability based on the federal return.
