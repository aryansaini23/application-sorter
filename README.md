# Citizen Application Sorter 📋

An AI-powered triage application built for government officers. Officers can upload a photo of a citizen's handwritten or printed application in any Indian language. The system reads the document, filters out narrative/emotional noise, extracts actionable details, and ranks urgency.

## Features
- **Multilingual OCR**: Digitises applications in 22+ Indian languages and English using **Sarvam Document Intelligence**.
- **Noise Filtering & Extraction**: Uses **sarvam-105b** to extract:
  - **Applicant Details**: Separate box for Name and Contact Number for follow-up.
  - **Work Requested**: Short, actionable bullet points describing the civic task.
  - **Department Responsible**: Civic/administrative body responsible for resolution.
  - **Priority (1 to 5)**: Color-coded triage score with a one-sentence rationale.
- **Language Toggle**: Choose output in **English** or **Hindi (हिन्दी)**.
- **Audit View**: Expandable panel to inspect raw OCR text.

---

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
Create a `.env` file in the project root (ensure it is never committed):
```env
SARVAM_API_KEY=your_sarvam_api_key_here
```

---

## How to Run

Start the Streamlit application:
```bash
streamlit run app.py
```

Open your browser at [http://localhost:8501](http://localhost:8501).
