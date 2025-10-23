from flask.views import MethodView
from flask_smorest import Blueprint, abort
from ..services.database_ops import get_summary_statistics
from ..schemas.invoice_schema import DashboardSummarySchema

blp = Blueprint(
    "Dashboard", "dashboard", url_prefix="/api/dashboard", description="Dashboard summary metrics"
)

@blp.route("/summary")
class DashboardSummary(MethodView):
    @blp.doc(summary="Get Dashboard Summary", description="Retrieves key summary metrics for the dashboard, including total invoices, counts by risk level, and average risk score.")
    @blp.response(200, DashboardSummarySchema)
    def get(self):
        """Get dashboard summary statistics"""
        try:
            summary = get_summary_statistics()
            return summary
        except Exception as e:
            abort(500, message=str(e))
