from flask import current_app, send_from_directory, request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint, abort
import os
from werkzeug.utils import secure_filename

from ..services.database_ops import get_all_invoices, get_invoice_by_id
from ..services.narrative_service import generate_narrative
from ..schemas.invoice_schema import InvoiceSchema, InvoiceQueryArgsSchema, NarrativeResponseSchema

blp = Blueprint(
    "Invoices", "invoices", url_prefix="/api/invoices", description="Operations on invoices"
)

from ..services.risk_engine import calculate_risk
from ..ingestion.ingestion import ingest_invoice_pdf
from ..services.database_ops import add_invoice_with_risk_factors

@blp.route("/upload")
class InvoiceUpload(MethodView):
    @blp.doc(summary="Upload and Process Invoice PDF", description="Upload an invoice PDF and provide an API key to process it in real-time.")
    @blp.response(201, InvoiceSchema)
    def post(self):
        """Upload and process an invoice PDF in real-time"""
        # --- DEBUGGING: Print the incoming request data ---
        print(f"Received form data: {request.form}")
        print(f"Received files: {request.files}")
        # --- END DEBUGGING ---

        if 'invoice_pdf' not in request.files:
            abort(400, message="No file part in the request. Key must be 'invoice_pdf'.")
        
        api_key = request.form.get('api_key')
        if not api_key:
            abort(400, message="No API key provided. Key must be 'api_key'.")

        file = request.files['invoice_pdf']
        if file.filename == '':
            abort(400, message="No selected file.")

        if not file.filename.endswith('.pdf'):
            abort(400, message="Invalid file type. Only PDF files are accepted.")

        # Define the absolute path for the "processed" directory
        processed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'processed'))
        
        # Ensure the directory exists
        os.makedirs(processed_dir, exist_ok=True)
        
        # Secure the filename and save the file
        s_filename = secure_filename(file.filename)
        file_path = os.path.join(processed_dir, s_filename)
        
        # Reset stream position and save the file
        file.stream.seek(0)
        file.save(file_path)
        
        # Reset stream position again before ingestion
        file.stream.seek(0)

        try:
            # 1. Ingest the PDF from the file stream
            ingested_data = ingest_invoice_pdf(file.stream, api_key)

            # 2. Calculate risk
            risk_score, risk_level, xai_factors = calculate_risk(ingested_data)

            # 3. Save to DB
            invoice_model_data = {
                'vendor_name': ingested_data['vendor_name'],
                'amount': ingested_data['total_amount'],
                'invoice_date': ingested_data['invoice_date'],
                'original_filename': s_filename,  # Use the secured filename
                'risk_score': risk_score,
                'risk_level': risk_level,
                'processing_status': 'Processed'
            }
            new_invoice = add_invoice_with_risk_factors(invoice_model_data, xai_factors)
            
            return new_invoice

        except Exception as e:
            current_app.logger.error(f"Invoice processing failed: {e}")
            abort(500, message=str(e))

@blp.route("/")
class InvoiceList(MethodView):
    @blp.doc(summary="List Invoices", description="Retrieves a list of all invoices, with optional filtering by risk level and sorting by invoice date.")
    @blp.arguments(InvoiceQueryArgsSchema, location="query")
    @blp.response(200, InvoiceSchema(many=True))
    def get(self, args):
        """List all invoices with optional filtering and sorting"""
        try:
            invoices = get_all_invoices(
                risk_level=args.get("risk_level"),
                sort_by_date=args.get("sort_by_date")
            )
            return invoices
        except Exception as e:
            # The debug print has been removed for production
            abort(500, message=str(e))

@blp.route("/<int:invoice_id>/pdf")
class InvoicePDF(MethodView):
    @blp.doc(summary="Get Invoice PDF", description="Serves the original PDF file for a given invoice.")
    def get(self, invoice_id):
        """Serve the original invoice PDF"""
        invoice = get_invoice_by_id(invoice_id)
        if not invoice or not invoice.original_filename:
            abort(404, message="PDF not found for this invoice.")
        
        processed_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'processed'))

        try:
            return send_from_directory(
                processed_dir,
                invoice.original_filename,
                as_attachment=False
            )
        except FileNotFoundError:
            abort(404, message="PDF file not found on server.")

@blp.route("/<int:invoice_id>/narrative")
class InvoiceNarrative(MethodView):
    @blp.doc(summary="Generate Invoice Narrative", description="Generates a human-readable summary for a specific invoice using a provided API key.")
    @blp.response(200, NarrativeResponseSchema)
    def post(self, invoice_id):
        """Generate a risk narrative for a specific invoice"""
        # --- DEBUGGING: Print the incoming request data ---
        print(f"Narrative request raw data: {request.data}")
        print(f"Narrative request parsed json: {request.json}")
        # --- END DEBUGGING ---

        api_key = request.json.get('api_key')
        if not api_key:
            abort(400, message="API key is required to generate a narrative.")

        invoice = get_invoice_by_id(invoice_id)
        if not invoice:
            abort(404, message=f"Invoice with ID {invoice_id} not found.")
        
        try:
            narrative_text = generate_narrative(invoice, api_key)
            return {"narrative": narrative_text}
        except Exception as e:
            abort(500, message=f"Failed to generate narrative: {str(e)}")

@blp.route("/risk/<string:risk_level>")
class InvoiceRiskFilter(MethodView):
    @blp.doc(summary="Filter Invoices by Risk Level", description="Retrieves a list of invoices filtered by a specific risk level.")
    @blp.response(200, InvoiceSchema(many=True))
    def get(self, risk_level):
        """Get invoices by risk level"""
        try:
            invoices = get_all_invoices(risk_level=risk_level)
            return invoices
        except Exception as e:
            abort(500, message=str(e))
