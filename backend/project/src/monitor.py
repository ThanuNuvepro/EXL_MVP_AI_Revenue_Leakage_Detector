import os
import sys
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- FIX: Add the 'project' directory to the Python path ---
# This allows all scripts to use the same absolute import style (e.g., 'from src.app...')
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from src.app import create_app, db
from src.app.ingestion.ingestion import ingest_invoice_pdf
from src.app.services.risk_engine import calculate_risk
from src.app.services.database_ops import add_invoice_with_risk_factors

# Define the directories
WATCH_DIR = os.path.join(os.path.dirname(__file__), 'invoice_inbox')
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), 'processed')
FAILED_DIR = os.path.join(os.path.dirname(__file__), 'failed')

# Create a Flask app instance for the database context
app = create_app()

class InvoiceEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        """Called when a file or directory is created."""
        if not event.is_directory and event.src_path.endswith('.pdf'):
            print(f"New PDF detected: {os.path.basename(event.src_path)}")
            self.process_invoice(event.src_path)

    def process_invoice(self, pdf_path):
        """Processes a single invoice PDF with detailed logging."""
        print(f"   [1/5] Starting processing for {os.path.basename(pdf_path)}")
        try:
            with app.app_context():
                # 1. Ingest the PDF
                print("   [2/5] Ingesting PDF data...")
                ingested_data = ingest_invoice_pdf(pdf_path)
                print("   [3/5] Ingestion successful. Assessing risk...")

                # 2. Calculate risk and get XAI factors
                risk_score, risk_level, xai_factors = calculate_risk(ingested_data)
                print(f"   [4/5] Risk assessment complete. Level: {risk_level}, Score: {risk_score}")

                # 3. Prepare data for database insertion
                invoice_model_data = {
                    'vendor_name': ingested_data['vendor_name'],
                    'amount': ingested_data['total_amount'],
                    'invoice_date': ingested_data['invoice_date'],
                    'original_filename': os.path.basename(pdf_path),
                    'risk_score': risk_score,
                    'risk_level': risk_level,
                    'processing_status': 'Processed'
                }

                # 4. Save to DB using the dedicated database operation
                print("   [5/5] Saving invoice and risk factors to database...")
                add_invoice_with_risk_factors(invoice_model_data, xai_factors)
                
                print(f"   [SUCCESS] Successfully stored invoice.")
                self.move_file(pdf_path, PROCESSED_DIR)

        except Exception as e:
            print(f"   [FAILED] An error occurred: {e}")
            import traceback
            traceback.print_exc()
            self.move_file(pdf_path, FAILED_DIR, "error")

    def move_file(self, src_path, dest_dir, prefix=""):
        """Moves a file to a destination directory, adding a prefix if needed."""
        if not os.path.exists(src_path):
            return
        
        filename = os.path.basename(src_path)
        new_filename = f"{prefix}_{filename}" if prefix else filename
        dest_path = os.path.join(dest_dir, new_filename)
        
        # Ensure destination filename is unique
        count = 1
        while os.path.exists(dest_path):
            name, ext = os.path.splitext(new_filename)
            dest_path = os.path.join(dest_dir, f"{name}_{count}{ext}")
            count += 1
            
        os.rename(src_path, dest_path)
        print(f"Moved '{filename}' to '{dest_dir}'")


if __name__ == "__main__":
    print(f"Starting invoice monitor. Watching directory: {WATCH_DIR}")
    
    # Ensure directories exist
    for d in [WATCH_DIR, PROCESSED_DIR, FAILED_DIR]:
        os.makedirs(d, exist_ok=True)

    event_handler = InvoiceEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print("Invoice monitor stopped.")