from flask import Flask

# 03lenio 18.06.2025 

def spawn():
    app = Flask(__name__)

    # Register blueprints/routes
    from .routes import api
    app.register_blueprint(api)

    return app
