from src.app import db
from datetime import date

class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = db.Column(db.Integer, primary_key=True)
    vendor_name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    processing_status = db.Column(db.String(50), nullable=False, default='Pending')
    risk_score = db.Column(db.Float, nullable=True)
    risk_level = db.Column(db.String(50), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True) # New field
    risk_factors = db.relationship('RiskFactor', backref='invoice', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f'<Invoice {self.id}>'

class RiskFactor(db.Model):
    __tablename__ = 'risk_factor'
    id = db.Column(db.Integer, primary_key=True)
    feature_name = db.Column(db.String(255), nullable=False)
    contribution = db.Column(db.Float, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)

    def __repr__(self):
        return f'<RiskFactor {self.feature_name}>'
