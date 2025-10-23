from src.app import db
from src.app.models.models import Invoice, RiskFactor
from sqlalchemy import func, desc, asc

def add_invoice_with_risk_factors(invoice_data, risk_factors_data):
    try:
        new_invoice = Invoice(**invoice_data)
        for rf_data in risk_factors_data:
            new_invoice.risk_factors.append(RiskFactor(**rf_data))
        
        db.session.add(new_invoice)
        db.session.commit()
        return new_invoice
    except Exception as e:
        db.session.rollback()
        raise e

from sqlalchemy.orm import aliased

def get_all_invoices(risk_level=None, sort_by_date=None):
    """
    Gets all invoices, ensuring uniqueness even with one-to-many relationships.
    """
    # --- FIX: Use a subquery to robustly select unique invoice IDs first ---
    # This is the most reliable way to prevent duplicates from the relationship join.
    subquery = db.session.query(Invoice.id).distinct().subquery()
    query = Invoice.query.join(subquery, Invoice.id == subquery.c.id)

    if risk_level:
        query = query.filter(Invoice.risk_level == risk_level)
    
    if sort_by_date:
        if sort_by_date.lower() == 'desc':
            query = query.order_by(desc(Invoice.invoice_date))
        else:
            query = query.order_by(asc(Invoice.invoice_date))
            
    return query.all()

def get_invoice_by_id(invoice_id):
    return Invoice.query.get(invoice_id)

def get_summary_statistics():
    total_invoices = db.session.query(func.count(Invoice.id)).scalar()
    
    risk_level_counts_query = db.session.query(
        Invoice.risk_level, 
        func.count(Invoice.id)
    ).group_by(Invoice.risk_level).all()
    
    risk_level_counts = {level: count for level, count in risk_level_counts_query if level is not None}
    
    average_risk_score = db.session.query(func.avg(Invoice.risk_score)).scalar()
    
    return {
        "total_invoices": total_invoices or 0,
        "invoices_per_risk_level": risk_level_counts,
        "average_risk_score": round(average_risk_score, 2) if average_risk_score is not None else 0.0
    }

def get_vendor_statistics(vendor_name, current_invoice_id=None):
    """
    Calculates historical statistics for a given vendor, excluding the current invoice.
    """
    query = db.session.query(
        func.avg(Invoice.amount),
        func.max(Invoice.amount)
    ).filter(Invoice.vendor_name == vendor_name)

    if current_invoice_id:
        query = query.filter(Invoice.id != current_invoice_id)

    stats = query.one()
    
    return {
        "avg_amount": stats[0] or 0.0,
        "max_amount": stats[1] or 0.0
    }
