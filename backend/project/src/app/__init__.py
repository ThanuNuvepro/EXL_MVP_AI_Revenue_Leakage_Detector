from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_smorest import Api
from dotenv import load_dotenv

db = SQLAlchemy()

def create_app():
    load_dotenv() # Load environment variables from .env file
    app = Flask(__name__, instance_relative_config=True)
    
    app.config.from_object('src.app.config.config.Config')
    app.config["API_TITLE"] = "Invoice Risk Assessment API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    db.init_app(app)
    api = Api(app)
    
    # Import and register blueprints
    from src.app.routes.invoice_routes import blp as InvoiceBlueprint
    from src.app.routes.dashboard_routes import blp as DashboardBlueprint
    from src.app.routes.vendor_routes import blp as VendorBlueprint
    api.register_blueprint(InvoiceBlueprint)
    api.register_blueprint(DashboardBlueprint)
    api.register_blueprint(VendorBlueprint)

    # Create database tables within the app context
    # This ensures models are registered correctly before creation
    with app.app_context():
        from src.app import models
        db.create_all()

    @app.route('/')
    def index():
        return redirect(url_for('api-docs.openapi_swagger_ui'))
        
    return app
