from flask.views import MethodView
from flask_smorest import Blueprint
from flask import jsonify

blp = Blueprint(
    "Vendors", "vendors", url_prefix="/api", description="Operations on vendors"
)

@blp.route("/vendors")
class VendorList(MethodView):
    def get(self):
        """List all vendors"""
        return jsonify([])
