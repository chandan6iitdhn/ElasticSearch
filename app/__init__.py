from flask import Flask


def create_app():
    app = Flask(__name__)

    # Import and register blueprints
    from app.routes import studies_bp
    app.register_blueprint(studies_bp)

    return app