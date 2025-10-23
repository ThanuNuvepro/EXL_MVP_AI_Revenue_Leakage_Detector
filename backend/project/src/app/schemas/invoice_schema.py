from marshmallow import Schema, fields, validate

class RiskFactorSchema(Schema):
    id = fields.Int(dump_only=True)
    feature_name = fields.Str(required=True)
    contribution = fields.Float(required=True)

class InvoiceSchema(Schema):
    invoice_id = fields.Int(dump_only=True, attribute="id")
    vendor_name = fields.Str(required=True)
    amount = fields.Float(required=True)
    invoice_date = fields.Date(required=True)
    processing_status = fields.Str(required=True)
    risk_score = fields.Float(allow_none=True)
    risk_level = fields.Str(allow_none=True)
    original_filename = fields.Str(allow_none=True) # New field
    risk_factors = fields.List(fields.Nested(RiskFactorSchema))

class InvoiceQueryArgsSchema(Schema):
    risk_level = fields.Str(
        required=False,
        validate=validate.OneOf(["Low", "Medium", "High"])
    )
    sort_by_date = fields.Str(
        required=False,
        validate=validate.OneOf(["asc", "desc"])
    )

class DashboardSummarySchema(Schema):
    total_invoices = fields.Int(required=True)
    invoices_per_risk_level = fields.Dict(keys=fields.Str(), values=fields.Int(), required=True)
    average_risk_score = fields.Float(required=True)

class NarrativeResponseSchema(Schema):
    narrative = fields.Str(required=True)
