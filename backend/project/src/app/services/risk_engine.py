from datetime import date

def calculate_risk(invoice_data: dict) -> tuple:
    """
    Simulates an ML model by assigning a risk score to an invoice and generating XAI factors.

    Args:
        invoice_data (dict): A dictionary containing validated invoice data.
                             Expected keys: 'total_amount', 'vendor_name', 'invoice_date'.

    Returns:
        tuple: A tuple containing the final risk score (float), the risk level (str),
               and a list of the generated XAI factor dictionaries.
    """
    risk_score = 0
    xai_factors = []

    if invoice_data.get('total_amount', 0) > 10000:
        points = 45
        risk_score += points
        xai_factors.append({
            'feature_name': 'High Invoice Amount',
            'contribution': points
        })

    vendor_name = invoice_data.get('vendor_name', '').lower()
    if 'consulting' in vendor_name or 'services' in vendor_name:
        points = 30
        risk_score += points
        xai_factors.append({
            'feature_name': 'Vendor Type',
            'contribution': points
        })

    invoice_date = invoice_data.get('invoice_date')
    if isinstance(invoice_date, date) and invoice_date.weekday() >= 5:
        points = 20
        risk_score += points
        xai_factors.append({
            'feature_name': 'Weekend Transaction',
            'contribution': points
        })

    if risk_score <= 30:
        risk_level = 'Low'
    elif 31 <= risk_score <= 60:
        risk_level = 'Medium'
    else:
        risk_level = 'High'

    return risk_score, risk_level, xai_factors
