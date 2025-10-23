import re
import pdfplumber
from datetime import datetime
from src.app.utils.exceptions import InvoiceValidationError
from openai import AzureOpenAI
import json
from flask import current_app

def ingest_invoice_pdf(file_stream, api_key: str, api_endpoint: str, deployment_name: str, model_name: str) -> dict:
    """
    Ingests an invoice PDF from a file stream, extracts text, and uses user-provided
    Azure OpenAI credentials to extract key information in a structured format.
    """
    # 1. Extract Raw Text using pdfplumber
    try:
        with pdfplumber.open(file_stream) as pdf:
            raw_text = ""
            for page in pdf.pages:
                raw_text += page.extract_text() or ""
        
        if not raw_text.strip():
            raise InvoiceValidationError("PDF is empty or contains no extractable text.")
            
    except Exception as e:
        current_app.logger.error(f"Failed to read or extract text from PDF stream: {e}")
        raise InvoiceValidationError(f"Could not process PDF file stream: {e}")

    # 2. Engineer the Prompt for the LLM
    prompt = f"""
    You are an expert data extraction AI. Your task is to read the raw text from an invoice and extract the following four fields: 'invoice_id', 'vendor_name', 'invoice_date', and 'total_amount'.

    Follow these rules precisely:
    1.  The 'invoice_date' must be in YYYY-MM-DD format.
    2.  The 'total_amount' must be a single number with a decimal point (e.g., 1234.56). Do not include currency symbols, commas, or any other text.
    3.  The 'vendor_name' should be the name of the company sending the invoice.
    4.  Your entire response must be ONLY the JSON object, with no other text, explanations, or markdown formatting.

    --- RAW INVOICE TEXT ---
    {raw_text}
    --- END RAW TEXT ---

    Now, provide the JSON object.
    """

    # 3. Call the LLM to perform the extraction
    try:
        client = AzureOpenAI(
            api_version="2024-02-01",
            azure_endpoint=api_endpoint,
            api_key=api_key,
        )
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0
        )
        
        response_content = response.choices[0].message.content
        
        # Clean the response to ensure it's valid JSON
        cleaned_response = response_content.strip().replace('```json', '').replace('```', '').strip()
        
        extracted_data = json.loads(cleaned_response)

    except Exception as e:
        current_app.logger.error(f"LLM extraction failed. Error: {e}")
        raise InvoiceValidationError(f"AI model failed to extract data from the invoice. Error: {e}")

    # 4. Validate and normalize the extracted data
    required_fields = ['invoice_id', 'vendor_name', 'invoice_date', 'total_amount']
    if not all(key in extracted_data for key in required_fields):
        missing_fields = [key for key in required_fields if key not in extracted_data]
        raise InvoiceValidationError(f"AI model did not return all required fields. Missing: {', '.join(missing_fields)}")

    try:
        validated_amount = float(extracted_data['total_amount'])
    except (ValueError, TypeError):
        raise InvoiceValidationError(f"Invalid amount format returned by AI: {extracted_data['total_amount']}")

    # Try parsing multiple common date formats
    validated_date = None
    possible_formats = ['%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y', '%b %d, %Y']
    for date_format in possible_formats:
        try:
            validated_date = datetime.strptime(extracted_data.get('invoice_date'), date_format).date()
            break  # Stop on the first successful parse
        except (ValueError, TypeError):
            continue
    
    if not validated_date:
        raise InvoiceValidationError(f"Invalid date format returned by AI: {extracted_data['invoice_date']}. Could not parse.")

    return {
        "invoice_id": extracted_data['invoice_id'],
        "vendor_name": extracted_data['vendor_name'],
        "invoice_date": validated_date,
        "total_amount": validated_amount
    }