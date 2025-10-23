class InvoiceValidationError(Exception):
    """Custom exception for invoice data validation errors."""
    def __init__(self, message="Invoice data validation failed"):
        self.message = message
        super().__init__(self.message)
